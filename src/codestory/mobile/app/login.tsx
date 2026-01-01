import { useState } from 'react';
import { View, Text, TextInput, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
      router.replace('/(authenticated)/dashboard');
    } catch (error: any) {
      Alert.alert('Login Failed', error.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View className="flex-1 bg-[#0d1117] px-6 pt-8">
      {/* Header */}
      <View className="mb-8">
        <Text className="text-3xl font-bold text-white">Welcome Back</Text>
        <Text className="text-gray-400 mt-2">Sign in to continue creating code stories</Text>
      </View>

      {/* Form */}
      <View className="gap-4">
        <View>
          <Text className="text-gray-300 mb-2">Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor="#6b7280"
            keyboardType="email-address"
            autoCapitalize="none"
            className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white"
          />
        </View>

        <View>
          <Text className="text-gray-300 mb-2">Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="Your password"
            placeholderTextColor="#6b7280"
            secureTextEntry
            className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white"
          />
        </View>

        <Pressable
          onPress={handleLogin}
          disabled={loading}
          className="bg-teal-500 py-4 rounded-xl items-center mt-4 active:bg-teal-600 disabled:opacity-50"
        >
          {loading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text className="text-white font-semibold text-lg">Sign In</Text>
          )}
        </Pressable>
      </View>

      {/* Register Link */}
      <View className="flex-row justify-center mt-8">
        <Text className="text-gray-400">Don't have an account? </Text>
        <Pressable onPress={() => router.push('/register')}>
          <Text className="text-teal-400 font-semibold">Sign up</Text>
        </Pressable>
      </View>
    </View>
  );
}
