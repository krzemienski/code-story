export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      api_keys: {
        Row: {
          created_at: string
          expires_at: string | null
          id: number
          is_active: boolean
          key_hash: string
          last_used_at: string | null
          name: string
          permissions: Json
          rate_limit: number
          user_id: string
        }
        Insert: {
          created_at?: string
          expires_at?: string | null
          id?: never
          is_active?: boolean
          key_hash: string
          last_used_at?: string | null
          name: string
          permissions?: Json
          rate_limit?: number
          user_id: string
        }
        Update: {
          created_at?: string
          expires_at?: string | null
          id?: never
          is_active?: boolean
          key_hash?: string
          last_used_at?: string | null
          name?: string
          permissions?: Json
          rate_limit?: number
          user_id?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          created_at: string
          email: string | null
          id: string
          is_superuser: boolean
          preferences: Json
          subscription_tier: string
          updated_at: string
          usage_quota: number
        }
        Insert: {
          created_at?: string
          email?: string | null
          id: string
          is_superuser?: boolean
          preferences?: Json
          subscription_tier?: string
          updated_at?: string
          usage_quota?: number
        }
        Update: {
          created_at?: string
          email?: string | null
          id?: string
          is_superuser?: boolean
          preferences?: Json
          subscription_tier?: string
          updated_at?: string
          usage_quota?: number
        }
        Relationships: []
      }
      repositories: {
        Row: {
          analysis_cache: Json
          created_at: string
          default_branch: string
          description: string | null
          id: number
          language: string | null
          last_analyzed_at: string | null
          name: string
          owner: string
          url: string
        }
        Insert: {
          analysis_cache?: Json
          created_at?: string
          default_branch?: string
          description?: string | null
          id?: never
          language?: string | null
          last_analyzed_at?: string | null
          name: string
          owner: string
          url: string
        }
        Update: {
          analysis_cache?: Json
          created_at?: string
          default_branch?: string
          description?: string | null
          id?: never
          language?: string | null
          last_analyzed_at?: string | null
          name?: string
          owner?: string
          url?: string
        }
        Relationships: []
      }
      stories: {
        Row: {
          audio_url: string | null
          completed_at: string | null
          created_at: string
          duration_seconds: number | null
          error_message: string | null
          focus_areas: Json
          id: number
          intent_id: number | null
          narrative_style: Database["public"]["Enums"]["narrative_style"]
          repository_id: number
          status: Database["public"]["Enums"]["story_status"]
          title: string
          transcript: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          audio_url?: string | null
          completed_at?: string | null
          created_at?: string
          duration_seconds?: number | null
          error_message?: string | null
          focus_areas?: Json
          id?: never
          intent_id?: number | null
          narrative_style?: Database["public"]["Enums"]["narrative_style"]
          repository_id: number
          status?: Database["public"]["Enums"]["story_status"]
          title: string
          transcript?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          audio_url?: string | null
          completed_at?: string | null
          created_at?: string
          duration_seconds?: number | null
          error_message?: string | null
          focus_areas?: Json
          id?: never
          intent_id?: number | null
          narrative_style?: Database["public"]["Enums"]["narrative_style"]
          repository_id?: number
          status?: Database["public"]["Enums"]["story_status"]
          title?: string
          transcript?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "fk_stories_intent"
            columns: ["intent_id"]
            isOneToOne: false
            referencedRelation: "story_intents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "stories_repository_id_fkey"
            columns: ["repository_id"]
            isOneToOne: false
            referencedRelation: "repositories"
            referencedColumns: ["id"]
          },
        ]
      }
      story_chapters: {
        Row: {
          audio_url: string | null
          created_at: string
          duration_seconds: number | null
          id: number
          order: number
          script: string
          start_time: number
          story_id: number
          title: string
        }
        Insert: {
          audio_url?: string | null
          created_at?: string
          duration_seconds?: number | null
          id?: never
          order: number
          script: string
          start_time?: number
          story_id: number
          title: string
        }
        Update: {
          audio_url?: string | null
          created_at?: string
          duration_seconds?: number | null
          id?: never
          order?: number
          script?: string
          start_time?: number
          story_id?: number
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "story_chapters_story_id_fkey"
            columns: ["story_id"]
            isOneToOne: false
            referencedRelation: "stories"
            referencedColumns: ["id"]
          },
        ]
      }
      story_intents: {
        Row: {
          conversation_history: Json
          created_at: string
          generated_plan: Json
          id: number
          identified_goals: Json
          preferences: Json
          repository_url: string
          updated_at: string
          user_id: string
        }
        Insert: {
          conversation_history?: Json
          created_at?: string
          generated_plan?: Json
          id?: never
          identified_goals?: Json
          preferences?: Json
          repository_url: string
          updated_at?: string
          user_id: string
        }
        Update: {
          conversation_history?: Json
          created_at?: string
          generated_plan?: Json
          id?: never
          identified_goals?: Json
          preferences?: Json
          repository_url?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      narrative_style:
        | "technical"
        | "storytelling"
        | "educational"
        | "casual"
        | "executive"
      story_status:
        | "pending"
        | "analyzing"
        | "generating"
        | "synthesizing"
        | "complete"
        | "failed"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DefaultSchema = Database[Extract<keyof Database, "public">]

export type Tables<
  TableName extends keyof DefaultSchema["Tables"]
> = DefaultSchema["Tables"][TableName]["Row"]

export type TablesInsert<
  TableName extends keyof DefaultSchema["Tables"]
> = DefaultSchema["Tables"][TableName]["Insert"]

export type TablesUpdate<
  TableName extends keyof DefaultSchema["Tables"]
> = DefaultSchema["Tables"][TableName]["Update"]

export type Enums<
  EnumName extends keyof DefaultSchema["Enums"]
> = DefaultSchema["Enums"][EnumName]
