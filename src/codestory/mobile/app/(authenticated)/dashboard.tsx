import { View, Text, Pressable, FlatList, ActivityIndicator, RefreshControl } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { getStories, Story } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

function StoryCard({ story }: { story: Story }) {
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-500/20 text-yellow-400',
    analyzing: 'bg-blue-500/20 text-blue-400',
    generating: 'bg-purple-500/20 text-purple-400',
    synthesizing: 'bg-indigo-500/20 text-indigo-400',
    complete: 'bg-green-500/20 text-green-400',
    failed: 'bg-red-500/20 text-red-400',
  };

  const statusColor = statusColors[story.status] || 'bg-gray-500/20 text-gray-400';
  const [bgColor, textColor] = statusColor.split(' ');

  return (
    <Pressable
      onPress={() => router.push(`/(authenticated)/story/${story.id}`)}
      className="bg-gray-800/50 p-4 rounded-xl mb-3 active:bg-gray-800"
    >
      <View className="flex-row items-center justify-between mb-2">
        <Text className="text-white font-semibold text-lg flex-1" numberOfLines={1}>
          {story.title}
        </Text>
        <View className={`px-2 py-1 rounded-full ${bgColor}`}>
          <Text className={textColor}>{story.status}</Text>
        </View>
      </View>
      <Text className="text-gray-400 text-sm">
        {new Date(story.created_at).toLocaleDateString()} • {story.narrative_style}
      </Text>
    </Pressable>
  );
}

export default function DashboardScreen() {
  const { logout } = useAuth();
  const { data: stories, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ['stories'],
    queryFn: getStories,
  });

  return (
    <View className="flex-1 bg-[#0d1117] px-4">
      {/* Header Actions */}
      <View className="flex-row justify-between items-center py-4">
        <Text className="text-gray-400">
          {stories?.length || 0} {stories?.length === 1 ? 'story' : 'stories'}
        </Text>
        <View className="flex-row gap-2">
          <Pressable
            onPress={() => router.push('/(authenticated)/new-story')}
            className="bg-teal-500 px-4 py-2 rounded-lg active:bg-teal-600"
          >
            <Text className="text-white font-semibold">+ New Story</Text>
          </Pressable>
          <Pressable
            onPress={logout}
            className="border border-gray-600 px-4 py-2 rounded-lg active:bg-gray-800"
          >
            <Text className="text-gray-400">Logout</Text>
          </Pressable>
        </View>
      </View>

      {/* Content */}
      {isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#14b8a6" />
        </View>
      ) : error ? (
        <View className="flex-1 items-center justify-center">
          <Text className="text-red-400 mb-4">Failed to load stories</Text>
          <Pressable
            onPress={() => refetch()}
            className="bg-teal-500 px-4 py-2 rounded-lg"
          >
            <Text className="text-white">Retry</Text>
          </Pressable>
        </View>
      ) : stories && stories.length > 0 ? (
        <FlatList
          data={stories}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => <StoryCard story={item} />}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor="#14b8a6"
            />
          }
          showsVerticalScrollIndicator={false}
        />
      ) : (
        <View className="flex-1 items-center justify-center">
          <Text className="text-gray-400 text-lg mb-2">No stories yet</Text>
          <Text className="text-gray-500 text-center mb-6">
            Create your first story from a GitHub repository
          </Text>
          <Pressable
            onPress={() => router.push('/(authenticated)/new-story')}
            className="bg-teal-500 px-6 py-3 rounded-xl active:bg-teal-600"
          >
            <Text className="text-white font-semibold">Create First Story</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
