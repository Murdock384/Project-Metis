import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { ScheduledEvent } from "../types";

interface EventActionModalProps {
  event: ScheduledEvent | null;
  onClose: () => void;
  onShift: (event: ScheduledEvent, minutes: number) => void;
  onResizeEnd: (event: ScheduledEvent, minutes: number) => void;
  onDelete: (event: ScheduledEvent) => void;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function EventActionModal({
  event,
  onClose,
  onShift,
  onResizeEnd,
  onDelete,
}: EventActionModalProps) {
  if (!event) {
    return null;
  }

  return (
    <Modal
      visible={!!event}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.title}>{event.task_title}</Text>
          <Text style={styles.subtitle}>
            {formatTime(event.start_time)} - {formatTime(event.end_time)}
            {event.category ? ` - ${event.category}` : ""}
          </Text>
          <Text style={styles.sourceLabel}>
            {event.source === "scheduler"
              ? "Placed by scheduler"
              : "Manually edited"}
          </Text>

          <View style={styles.rowGroup}>
            <Text style={styles.groupLabel}>Move</Text>
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => onShift(event, -15)}
              >
                <Text style={styles.actionButtonText}>-15 min</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => onShift(event, 15)}
              >
                <Text style={styles.actionButtonText}>+15 min</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.rowGroup}>
            <Text style={styles.groupLabel}>Resize (end time)</Text>
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => onResizeEnd(event, -15)}
              >
                <Text style={styles.actionButtonText}>-15 min</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => onResizeEnd(event, 15)}
              >
                <Text style={styles.actionButtonText}>+15 min</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={styles.deleteButton}
              onPress={() => onDelete(event)}
            >
              <Text style={styles.deleteButtonText}>Delete</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.closeButton} onPress={onClose}>
              <Text style={styles.closeButtonText}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    alignItems: "center",
  },
  sheet: {
    backgroundColor: "white",
    borderRadius: 16,
    padding: 20,
    width: "85%",
  },
  title: {
    fontSize: 17,
    fontWeight: "600",
  },
  subtitle: {
    fontSize: 14,
    color: "#444",
    marginTop: 4,
  },
  sourceLabel: {
    fontSize: 12,
    color: "#888",
    marginTop: 2,
    marginBottom: 12,
  },
  rowGroup: {
    marginTop: 8,
  },
  groupLabel: {
    fontSize: 12,
    color: "#666",
    marginBottom: 6,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
  },
  actionButton: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  actionButtonText: {
    color: "#333",
  },
  actionsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 20,
  },
  deleteButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: "#fee2e2",
  },
  deleteButtonText: {
    color: "#b91c1c",
    fontWeight: "600",
  },
  closeButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  closeButtonText: {
    color: "#444",
  },
});
