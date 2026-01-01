import * as SecureStore from "expo-secure-store";

export async function saveToken(token: string): Promise<void> {
  await SecureStore.setItemAsync("token", token);
}

export async function getToken(): Promise<string | null> {
  return await SecureStore.getItemAsync("token");
}

export async function removeToken(): Promise<void> {
  await SecureStore.deleteItemAsync("token");
}

export async function saveUser(user: any): Promise<void> {
  await SecureStore.setItemAsync("user", JSON.stringify(user));
}

export async function getUser(): Promise<any | null> {
  const user = await SecureStore.getItemAsync("user");
  return user ? JSON.parse(user) : null;
}

export async function clearAuth(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync("token"),
    SecureStore.deleteItemAsync("user"),
  ]);
}
