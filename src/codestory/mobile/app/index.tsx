import { View, Text, Pressable, ScrollView } from 'react-native';
import { Link, router } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';
import { useEffect } from 'react';

export default function HomeScreen() {
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/(authenticated)/dashboard');
    }
  }, [isAuthenticated, isLoading]);

  return (
    <ScrollView className="flex-1 bg-[#0d1117]">
      <View className="flex-1 px-6 pt-16 pb-8">
        {/* Header */}
        <View className="items-center mb-8">
          <Text className="text-4xl font-bold text-white text-center">
            Code Story
          </Text>
          <View className="mt-2 px-3 py-1 bg-teal-500/20 rounded-full">
            <Text className="text-teal-400 text-sm">Powered by AI</Text>
          </View>
        </View>

        {/* Hero */}
        <View className="items-center mb-12">
          <Text className="text-3xl font-bold text-white text-center mb-4">
            Transform Code into{'\n'}
            <Text className="text-teal-400">Compelling Stories</Text>
          </Text>
          <Text className="text-gray-400 text-center text-lg px-4">
            Turn any GitHub repository into engaging audio narratives.
            Understand codebases through storytelling.
          </Text>
        </View>

        {/* CTA Buttons */}
        <View className="gap-4 mb-12">
          <Pressable
            onPress={() => router.push('/login')}
            className="bg-teal-500 py-4 rounded-xl items-center active:bg-teal-600"
          >
            <Text className="text-white font-semibold text-lg">Get Started</Text>
          </Pressable>
          <Pressable
            onPress={() => router.push('/register')}
            className="border border-teal-500 py-4 rounded-xl items-center active:bg-teal-500/10"
          >
            <Text className="text-teal-400 font-semibold text-lg">Create Account</Text>
          </Pressable>
        </View>

        {/* How It Works */}
        <View className="mb-8">
          <Text className="text-2xl font-bold text-white text-center mb-6">
            How It Works
          </Text>

          <View className="gap-4">
            <View className="bg-gray-800/50 p-4 rounded-xl">
              <Text className="text-teal-400 font-bold text-lg mb-1">1. Connect Repository</Text>
              <Text className="text-gray-400">
                Paste any GitHub URL and we'll analyze the codebase
              </Text>
            </View>

            <View className="bg-gray-800/50 p-4 rounded-xl">
              <Text className="text-teal-400 font-bold text-lg mb-1">2. AI Narrates</Text>
              <Text className="text-gray-400">
                Our agents create a compelling narrative tailored to your style
              </Text>
            </View>

            <View className="bg-gray-800/50 p-4 rounded-xl">
              <Text className="text-teal-400 font-bold text-lg mb-1">3. Listen & Learn</Text>
              <Text className="text-gray-400">
                Audio stories you can enjoy anywhere — commute, gym, or relaxing
              </Text>
            </View>
          </View>
        </View>

        {/* Footer */}
        <View className="items-center pt-8 border-t border-gray-800">
          <Text className="text-gray-500">Code Story — Transform code into stories</Text>
        </View>
      </View>
    </ScrollView>
  );
}
