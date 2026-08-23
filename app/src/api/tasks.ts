import { apiClient } from "./client";
import { ScheduleRunResult, Task, TaskCreatePayload } from "../types";

export async function fetchTasks(status?: string): Promise<Task[]> {
  const { data } = await apiClient.get<Task[]>("/tasks", {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function createTask(payload: TaskCreatePayload): Promise<Task> {
  const { data } = await apiClient.post<Task>("/tasks", payload);
  return data;
}

export async function deleteTask(id: number): Promise<void> {
  await apiClient.delete(`/tasks/${id}`);
}

export async function runScheduler(): Promise<ScheduleRunResult> {
  const { data } = await apiClient.post<ScheduleRunResult>("/tasks/schedule");
  return data;
}
