import { apiClient } from "./client";
import {
  EventCreatePayload,
  EventUpdatePayload,
  ScheduledEvent,
} from "../types";

export async function fetchEvents(): Promise<ScheduledEvent[]> {
  const { data } = await apiClient.get<ScheduledEvent[]>("/events");
  return data;
}

export async function createEvent(
  payload: EventCreatePayload,
): Promise<ScheduledEvent> {
  const { data } = await apiClient.post<ScheduledEvent>("/events", payload);
  return data;
}

export async function updateEvent(
  id: number,
  payload: EventUpdatePayload,
): Promise<ScheduledEvent> {
  const { data } = await apiClient.patch<ScheduledEvent>(
    `/events/${id}`,
    payload,
  );
  return data;
}

export async function deleteEvent(id: number): Promise<void> {
  await apiClient.delete(`/events/${id}`);
}
