import axios from "axios";
import * as SecureStore from "expo-secure-store";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000/api";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await SecureStore.deleteItemAsync("token");
    }
    return Promise.reject(error);
  }
);

// Story types
export interface Story {
  id: number;
  title: string;
  status: 'pending' | 'analyzing' | 'generating' | 'synthesizing' | 'complete' | 'failed';
  narrative_style: 'technical' | 'storytelling' | 'educational' | 'casual' | 'executive';
  created_at: string;
}

export interface StoryChapter {
  id: number;
  story_id: number;
  order: number;
  title: string | null;
  script: string | null;
  audio_url: string | null;
  duration_seconds: number | null;
}

// API functions
export async function getStories(): Promise<Story[]> {
  const response = await api.get('/stories');
  return response.data;
}

export async function getStory(id: number): Promise<Story> {
  const response = await api.get(`/stories/${id}`);
  return response.data;
}

export async function getChapters(storyId: number): Promise<StoryChapter[]> {
  const response = await api.get(`/stories/${storyId}/chapters`);
  return response.data;
}

export async function createStory(data: {
  repo_url: string;
  narrative_style: string;
  conversation?: Array<{ role: string; content: string }>;
}): Promise<Story> {
  const response = await api.post('/stories', data);
  return response.data;
}

export async function deleteStory(id: number): Promise<void> {
  await api.delete(`/stories/${id}`);
}
