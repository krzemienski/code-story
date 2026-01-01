import { useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, Alert } from 'react-native';
import { router } from 'expo-router';
import { createStory } from '@/lib/api';

const NARRATIVE_STYLES = [
  { id: 'technical', label: 'Technical', description: 'Detailed technical explanation' },
  { id: 'storytelling', label: 'Storytelling', description: 'Narrative-driven journey' },
  { id: 'educational', label: 'Educational', description: 'Learning-focused approach' },
  { id: 'casual', label: 'Casual', description: 'Friendly, conversational tone' },
  { id: 'executive', label: 'Executive', description: 'High-level overview' },
];

const VOICE_PROFILES = [
  { id: 'rachel', label: 'Rachel', description: 'Clear and technical' },
  { id: 'bella', label: 'Bella', description: 'Warm and conversational' },
  { id: 'daniel', label: 'Daniel', description: 'Calm and educational' },
];

export default function NewStoryScreen() {
  const [repoUrl, setRepoUrl] = useState('');
  const [selectedStyle, setSelectedStyle] = useState('storytelling');
  const [selectedVoice, setSelectedVoice] = useState('rachel');
  const [loading, setLoading] = useState(false);

  const isValidGitHubUrl = (url: string) => {
    return /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?/.test(url);
  };

  async function handleCreate() {
    if (!repoUrl) {
      Alert.alert('Error', 'Please enter a GitHub URL');
      return;
    }

    if (!isValidGitHubUrl(repoUrl)) {
      Alert.alert('Error', 'Please enter a valid GitHub repository URL');
      return;
    }

    setLoading(true);
    try {
      const story = await createStory({
        repo_url: repoUrl,
        narrative_style: selectedStyle,
      });
      router.replace(`/(authenticated)/story/${story.id}`);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create story');
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView className="flex-1 bg-[#0d1117]">
      <View className="px-4 py-6">
        {/* GitHub URL Input */}
        <View className="mb-6">
          <Text className="text-white font-semibold text-lg mb-2">GitHub Repository</Text>
          <Text className="text-gray-400 mb-3">
            Paste the URL of the repository you want to turn into a story
          </Text>
          <TextInput
            value={repoUrl}
            onChangeText={setRepoUrl}
            placeholder="https://github.com/owner/repo"
            placeholderTextColor="#6b7280"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white"
          />
          {repoUrl && !isValidGitHubUrl(repoUrl) && (
            <Text className="text-red-400 mt-2 text-sm">
              Please enter a valid GitHub URL (e.g., https://github.com/owner/repo)
            </Text>
          )}
        </View>

        {/* Narrative Style Selection */}
        <View className="mb-6">
          <Text className="text-white font-semibold text-lg mb-2">Narrative Style</Text>
          <Text className="text-gray-400 mb-3">
            Choose how you want the story to be told
          </Text>
          <View className="gap-2">
            {NARRATIVE_STYLES.map((style) => (
              <Pressable
                key={style.id}
                onPress={() => setSelectedStyle(style.id)}
                className={`p-4 rounded-xl border ${
                  selectedStyle === style.id
                    ? 'border-teal-500 bg-teal-500/10'
                    : 'border-gray-700 bg-gray-800/50'
                }`}
              >
                <View className="flex-row items-center justify-between">
                  <View className="flex-1">
                    <Text className={`font-semibold ${
                      selectedStyle === style.id ? 'text-teal-400' : 'text-white'
                    }`}>
                      {style.label}
                    </Text>
                    <Text className="text-gray-400 text-sm mt-1">
                      {style.description}
                    </Text>
                  </View>
                  <View className={`w-5 h-5 rounded-full border-2 ${
                    selectedStyle === style.id
                      ? 'border-teal-500 bg-teal-500'
                      : 'border-gray-600'
                  }`}>
                    {selectedStyle === style.id && (
                      <View className="flex-1 items-center justify-center">
                        <Text className="text-white text-xs">✓</Text>
                      </View>
                    )}
                  </View>
                </View>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Voice Selection */}
        <View className="mb-6">
          <Text className="text-white font-semibold text-lg mb-2">Voice</Text>
          <Text className="text-gray-400 mb-3">
            Select the narrator voice for your story
          </Text>
          <View className="flex-row gap-2">
            {VOICE_PROFILES.map((voice) => (
              <Pressable
                key={voice.id}
                onPress={() => setSelectedVoice(voice.id)}
                className={`flex-1 p-3 rounded-xl border ${
                  selectedVoice === voice.id
                    ? 'border-teal-500 bg-teal-500/10'
                    : 'border-gray-700 bg-gray-800/50'
                }`}
              >
                <Text className={`font-semibold text-center ${
                  selectedVoice === voice.id ? 'text-teal-400' : 'text-white'
                }`}>
                  {voice.label}
                </Text>
                <Text className="text-gray-400 text-xs text-center mt-1">
                  {voice.description}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Create Button */}
        <Pressable
          onPress={handleCreate}
          disabled={loading || !repoUrl || !isValidGitHubUrl(repoUrl)}
          className="bg-teal-500 py-4 rounded-xl items-center active:bg-teal-600 disabled:opacity-50"
        >
          {loading ? (
            <View className="flex-row items-center gap-2">
              <ActivityIndicator color="white" size="small" />
              <Text className="text-white font-semibold text-lg">Creating Story...</Text>
            </View>
          ) : (
            <Text className="text-white font-semibold text-lg">Generate Story</Text>
          )}
        </Pressable>

        {/* Info */}
        <View className="mt-6 p-4 bg-gray-800/50 rounded-xl">
          <Text className="text-gray-400 text-sm text-center">
            Story generation typically takes 2-5 minutes depending on repository size.
            You'll be notified when it's ready.
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}
