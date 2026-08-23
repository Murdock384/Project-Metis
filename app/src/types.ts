export type TaskStatus = "pending" | "scheduled" | "done";

export interface Task {
  id: number;
  user_id: number;
  title: string;
  difficulty: number;
  urgency: number;
  estimated_minutes: number;
  category: string | null;
  status: TaskStatus;
  created_at: string;
}

export interface TaskCreatePayload {
  title: string;
  difficulty: number;
  urgency: number;
  estimated_minutes: number;
  category?: string | null;
}

export interface ScheduledEvent {
  id: number;
  task_id: number;
  task_title: string;
  category: string | null;
  start_time: string;
  end_time: string;
  source: "scheduler" | "manual";
  calendar_event_id: string | null;
}

export interface EventCreatePayload {
  task_id?: number;
  title?: string;
  difficulty?: number;
  urgency?: number;
  category?: string;
  start_time: string;
  end_time: string;
}

export interface EventUpdatePayload {
  start_time?: string;
  end_time?: string;
}

export interface ScheduleRunResult {
  scheduled_count: number;
  skipped_count: number;
  events: ScheduledEvent[];
}
