export type AgentUsed =
  | 'Knowledge'
  | 'Analytics'
  | 'PersonalAdvisor'
  | 'team'
  | 'error'
  | string;

export type ChatRequest = {
  user_id: string;
  session_id?: string | null;
  message: string;
};

export type ChatResponse = {
  session_id: string;
  agent_used: AgentUsed;
  response: string;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent_used?: AgentUsed | null;
};

export type ChatHistoryMessage = Omit<ChatMessage, 'id'>;

export type ChatHistoryResponse = {
  session_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: ChatHistoryMessage[];
};

export type ChatSession = {
  session_id: string;
  user_id: string;
  messages: ChatMessage[];
};
