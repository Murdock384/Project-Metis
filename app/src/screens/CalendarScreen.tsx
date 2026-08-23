import { useState } from "react";
import {
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar } from "react-native-big-calendar";
import {
  createEvent,
  deleteEvent,
  fetchEvents,
  updateEvent,
} from "../api/events";
import { createTask, fetchTasks, runScheduler } from "../api/tasks";
import {
  EventCreatePayload,
  EventUpdatePayload,
  ScheduledEvent,
} from "../types";
import { TaskFormModal, TaskFormValues } from "../components/TaskFormModal";
import { EventActionModal } from "../components/EventActionModal";

interface CalendarEvent {
  title: string;
  start: Date;
  end: Date;
  raw: ScheduledEvent;
}

export function CalendarScreen() {
  const queryClient = useQueryClient();
  const [addTaskVisible, setAddTaskVisible] = useState(false);
  const [quickAddStart, setQuickAddStart] = useState<Date | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<ScheduledEvent | null>(
    null,
  );

  const eventsQuery = useQuery({ queryKey: ["events"], queryFn: fetchEvents });
  const pendingTasksQuery = useQuery({
    queryKey: ["tasks", "pending"],
    queryFn: () => fetchTasks("pending"),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["events"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const createTaskMutation = useMutation({
    mutationFn: createTask,
    onSuccess: invalidateAll,
  });

  const runSchedulerMutation = useMutation({
    mutationFn: runScheduler,
    onSuccess: invalidateAll,
  });

  const createEventMutation = useMutation({
    mutationFn: (payload: EventCreatePayload) => createEvent(payload),
    onSuccess: invalidateAll,
  });

  const updateEventMutation = useMutation({
    mutationFn: (vars: { id: number; payload: EventUpdatePayload }) =>
      updateEvent(vars.id, vars.payload),
    onSuccess: invalidateAll,
  });

  const deleteEventMutation = useMutation({
    mutationFn: (id: number) => deleteEvent(id),
    onSuccess: invalidateAll,
  });

  const calendarEvents: CalendarEvent[] = (eventsQuery.data ?? []).map(
    (event) => ({
      title: event.task_title,
      start: new Date(event.start_time),
      end: new Date(event.end_time),
      raw: event,
    }),
  );

  const handleAddTaskSubmit = (values: TaskFormValues) => {
    createTaskMutation.mutate({
      title: values.title,
      difficulty: values.difficulty,
      urgency: values.urgency,
      estimated_minutes: values.estimated_minutes,
      category: values.category || undefined,
    });
    setAddTaskVisible(false);
  };

  const handleQuickAddSubmit = (values: TaskFormValues) => {
    if (!quickAddStart) return;
    const endTime = new Date(
      quickAddStart.getTime() + values.estimated_minutes * 60_000,
    );
    createEventMutation.mutate({
      title: values.title,
      difficulty: values.difficulty,
      urgency: values.urgency,
      category: values.category || undefined,
      start_time: quickAddStart.toISOString(),
      end_time: endTime.toISOString(),
    });
    setQuickAddStart(null);
  };

  const handleShift = (event: ScheduledEvent, minutes: number) => {
    const newStart = new Date(
      new Date(event.start_time).getTime() + minutes * 60_000,
    );
    const newEnd = new Date(
      new Date(event.end_time).getTime() + minutes * 60_000,
    );
    updateEventMutation.mutate({
      id: event.id,
      payload: {
        start_time: newStart.toISOString(),
        end_time: newEnd.toISOString(),
      },
    });
    setSelectedEvent(null);
  };

  const handleResizeEnd = (event: ScheduledEvent, minutes: number) => {
    const newEnd = new Date(
      new Date(event.end_time).getTime() + minutes * 60_000,
    );
    if (newEnd <= new Date(event.start_time)) return;
    updateEventMutation.mutate({
      id: event.id,
      payload: { end_time: newEnd.toISOString() },
    });
    setSelectedEvent(null);
  };

  const handleDelete = (event: ScheduledEvent) => {
    deleteEventMutation.mutate(event.id);
    setSelectedEvent(null);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Metis Calendar</Text>
        <View style={styles.headerButtons}>
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => runSchedulerMutation.mutate()}
            disabled={runSchedulerMutation.isPending}
          >
            <Text style={styles.headerButtonText}>
              {runSchedulerMutation.isPending
                ? "Scheduling..."
                : `Schedule pending (${pendingTasksQuery.data?.length ?? 0})`}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => setAddTaskVisible(true)}
          >
            <Text style={styles.headerButtonText}>+ Task</Text>
          </TouchableOpacity>
        </View>
      </View>

      <Calendar<CalendarEvent>
        events={calendarEvents}
        height={600}
        mode="3days"
        swipeEnabled
        onPressEvent={(event) => setSelectedEvent(event.raw)}
        onPressCell={(date) => setQuickAddStart(date)}
      />

      <TaskFormModal
        visible={addTaskVisible}
        heading="Add Task (goes to pending pool)"
        onClose={() => setAddTaskVisible(false)}
        onSubmit={handleAddTaskSubmit}
      />

      <TaskFormModal
        visible={!!quickAddStart}
        heading="Quick Add Event"
        onClose={() => setQuickAddStart(null)}
        onSubmit={handleQuickAddSubmit}
      />

      <EventActionModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        onShift={handleShift}
        onResizeEnd={handleResizeEnd}
        onDelete={handleDelete}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 8,
  },
  headerButtons: {
    flexDirection: "row",
    gap: 8,
  },
  headerButton: {
    backgroundColor: "#2563eb",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  headerButtonText: {
    color: "white",
    fontWeight: "600",
    fontSize: 13,
  },
});
