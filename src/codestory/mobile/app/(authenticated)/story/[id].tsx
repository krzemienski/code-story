import { useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, Alert } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Audio } from 'expo-av';
import { getStory, getChapters, deleteStory, Story, StoryChapter } from '@/lib/api';

function ChapterItem({
  chapter,
  isPlaying,
  onPlay,
}: {
  chapter: StoryChapter;
  isPlaying: boolean;
  onPlay: () => void;
}) {
  return (
    <Pressable
      onPress={onPlay}
      className={`p-4 rounded-xl mb-2 ${
        isPlaying ? 'bg-teal-500/20 border border-teal-500' : 'bg-gray-800/50'
      }`}
    >
      <View className="flex-row items-center gap-3">
        <View className={`w-10 h-10 rounded-full items-center justify-center ${
          isPlaying ? 'bg-teal-500' : 'bg-gray-700'
        }`}>
          <Text className="text-white font-bold">{chapter.order}</Text>
        </View>
        <View className="flex-1">
          <Text className={`font-semibold ${isPlaying ? 'text-teal-400' : 'text-white'}`}>
            {chapter.title || `Chapter ${chapter.order}`}
          </Text>
          {chapter.duration_seconds && (
            <Text className="text-gray-400 text-sm">
              {Math.floor(chapter.duration_seconds / 60)}:{String(chapter.duration_seconds % 60).padStart(2, '0')}
            </Text>
          )}
        </View>
        <Text className={isPlaying ? 'text-teal-400' : 'text-gray-400'}>
          {isPlaying ? '▶' : '○'}
        </Text>
      </View>
    </Pressable>
  );
}

export default function StoryDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [sound, setSound] = useState<Audio.Sound | null>(null);
  const [currentChapter, setCurrentChapter] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const { data: story, isLoading: storyLoading } = useQuery({
    queryKey: ['story', id],
    queryFn: () => getStory(Number(id)),
    enabled: !!id,
  });

  const { data: chapters, isLoading: chaptersLoading } = useQuery({
    queryKey: ['chapters', id],
    queryFn: () => getChapters(Number(id)),
    enabled: !!id,
  });

  useEffect(() => {
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, [sound]);

  async function playChapter(chapter: StoryChapter) {
    if (!chapter.audio_url) {
      Alert.alert('Audio Not Available', 'This chapter does not have audio yet.');
      return;
    }

    try {
      // Stop current audio
      if (sound) {
        await sound.stopAsync();
        await sound.unloadAsync();
      }

      // Load and play new audio
      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: chapter.audio_url },
        { shouldPlay: true }
      );
      setSound(newSound);
      setCurrentChapter(chapter.order);
      setIsPlaying(true);

      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setIsPlaying(false);
          setCurrentChapter(null);
        }
      });
    } catch (error) {
      console.error('Failed to play audio:', error);
      Alert.alert('Playback Error', 'Could not play audio');
    }
  }

  async function togglePlayPause() {
    if (!sound) return;

    if (isPlaying) {
      await sound.pauseAsync();
      setIsPlaying(false);
    } else {
      await sound.playAsync();
      setIsPlaying(true);
    }
  }

  async function handleDelete() {
    Alert.alert(
      'Delete Story',
      'Are you sure you want to delete this story? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteStory(Number(id));
              router.replace('/(authenticated)/dashboard');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete story');
            }
          },
        },
      ]
    );
  }

  if (storyLoading || chaptersLoading) {
    return (
      <View className="flex-1 bg-[#0d1117] items-center justify-center">
        <ActivityIndicator size="large" color="#14b8a6" />
      </View>
    );
  }

  if (!story) {
    return (
      <View className="flex-1 bg-[#0d1117] items-center justify-center">
        <Text className="text-red-400">Story not found</Text>
      </View>
    );
  }

  const statusColors: Record<string, { bg: string; text: string }> = {
    pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
    analyzing: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
    generating: { bg: 'bg-purple-500/20', text: 'text-purple-400' },
    synthesizing: { bg: 'bg-indigo-500/20', text: 'text-indigo-400' },
    complete: { bg: 'bg-green-500/20', text: 'text-green-400' },
    failed: { bg: 'bg-red-500/20', text: 'text-red-400' },
  };

  const status = statusColors[story.status] || { bg: 'bg-gray-500/20', text: 'text-gray-400' };

  return (
    <View className="flex-1 bg-[#0d1117]">
      <ScrollView className="flex-1 px-4 py-4">
        {/* Story Header */}
        <View className="mb-6">
          <Text className="text-2xl font-bold text-white mb-2">{story.title}</Text>
          <View className="flex-row items-center gap-3">
            <View className={`px-3 py-1 rounded-full ${status.bg}`}>
              <Text className={status.text}>{story.status}</Text>
            </View>
            <Text className="text-gray-400">{story.narrative_style}</Text>
          </View>
        </View>

        {/* Progress for In-Progress Stories */}
        {['pending', 'analyzing', 'generating', 'synthesizing'].includes(story.status) && (
          <View className="bg-gray-800/50 p-4 rounded-xl mb-6">
            <View className="flex-row items-center gap-3 mb-2">
              <ActivityIndicator size="small" color="#14b8a6" />
              <Text className="text-white font-semibold">Generating your story...</Text>
            </View>
            <Text className="text-gray-400 text-sm">
              This typically takes 2-5 minutes. Feel free to leave and come back.
            </Text>
          </View>
        )}

        {/* Chapters */}
        {chapters && chapters.length > 0 && (
          <View className="mb-6">
            <Text className="text-white font-semibold text-lg mb-3">
              Chapters ({chapters.length})
            </Text>
            {chapters.map((chapter) => (
              <ChapterItem
                key={chapter.id}
                chapter={chapter}
                isPlaying={currentChapter === chapter.order && isPlaying}
                onPlay={() => playChapter(chapter)}
              />
            ))}
          </View>
        )}

        {/* No Chapters Yet */}
        {(!chapters || chapters.length === 0) && story.status === 'complete' && (
          <View className="bg-gray-800/50 p-4 rounded-xl mb-6">
            <Text className="text-gray-400 text-center">
              No chapters available yet.
            </Text>
          </View>
        )}

        {/* Delete Button */}
        <Pressable
          onPress={handleDelete}
          className="border border-red-500/50 py-3 rounded-xl items-center mt-4 active:bg-red-500/10"
        >
          <Text className="text-red-400 font-semibold">Delete Story</Text>
        </Pressable>
      </ScrollView>

      {/* Audio Player Bar */}
      {currentChapter !== null && (
        <View className="bg-gray-900 border-t border-gray-800 px-4 py-4">
          <View className="flex-row items-center gap-4">
            <Pressable
              onPress={togglePlayPause}
              className="w-12 h-12 bg-teal-500 rounded-full items-center justify-center"
            >
              <Text className="text-white text-xl">{isPlaying ? '⏸' : '▶'}</Text>
            </Pressable>
            <View className="flex-1">
              <Text className="text-white font-semibold">
                Chapter {currentChapter}
              </Text>
              <Text className="text-gray-400 text-sm">
                {isPlaying ? 'Now playing' : 'Paused'}
              </Text>
            </View>
          </View>
        </View>
      )}
    </View>
  );
}
