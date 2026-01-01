import { Stack, router } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';
import { useEffect } from 'react';
import { View, ActivityIndicator } from 'react-native';

export default function AuthenticatedLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <View className="flex-1 bg-[#0d1117] items-center justify-center">
        <ActivityIndicator size="large" color="#14b8a6" />
      </View>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: '#0d1117' },
        headerTintColor: '#14b8a6',
        headerTitleStyle: { fontWeight: 'bold' },
        contentStyle: { backgroundColor: '#0d1117' },
      }}
    >
      <Stack.Screen
        name="dashboard"
        options={{
          title: 'My Stories',
          headerRight: () => null, // Will add logout button later
        }}
      />
      <Stack.Screen
        name="new-story"
        options={{ title: 'New Story' }}
      />
      <Stack.Screen
        name="story/[id]"
        options={{ title: 'Story' }}
      />
    </Stack>
  );
}
