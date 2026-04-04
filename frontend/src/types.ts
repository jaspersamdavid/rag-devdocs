export interface SourceChunk {
  source: string;
  content: string;
  distance: number | null;
}

export interface AskResponse {
  answer: string;
  sources: SourceChunk[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceChunk[];
  isLoading?: boolean;
}