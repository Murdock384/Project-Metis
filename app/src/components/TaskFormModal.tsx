import { useState } from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

export interface TaskFormValues {
  title: string;
  difficulty: number;
  urgency: number;
  estimated_minutes: number;
  category: string;
}

interface TaskFormModalProps {
  visible: boolean;
  heading: string;
  onClose: () => void;
  onSubmit: (values: TaskFormValues) => void;
}

const RATING_OPTIONS = [1, 2, 3, 4, 5];

function RatingPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.ratingRow}>
        {RATING_OPTIONS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[
              styles.ratingButton,
              value === option && styles.ratingButtonSelected,
            ]}
            onPress={() => onChange(option)}
          >
            <Text
              style={
                value === option ? styles.ratingTextSelected : styles.ratingText
              }
            >
              {option}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

export function TaskFormModal({
  visible,
  heading,
  onClose,
  onSubmit,
}: TaskFormModalProps) {
  const [title, setTitle] = useState("");
  const [difficulty, setDifficulty] = useState(3);
  const [urgency, setUrgency] = useState(3);
  const [estimatedMinutes, setEstimatedMinutes] = useState("30");
  const [category, setCategory] = useState("");

  const reset = () => {
    setTitle("");
    setDifficulty(3);
    setUrgency(3);
    setEstimatedMinutes("30");
    setCategory("");
  };

  const handleSubmit = () => {
    const minutes = parseInt(estimatedMinutes, 10);
    if (!title.trim() || Number.isNaN(minutes) || minutes <= 0) {
      return;
    }
    onSubmit({
      title: title.trim(),
      difficulty,
      urgency,
      estimated_minutes: minutes,
      category,
    });
    reset();
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.heading}>{heading}</Text>

          <Text style={styles.label}>Title</Text>
          <TextInput
            style={styles.input}
            value={title}
            onChangeText={setTitle}
            placeholder="e.g. Write thesis intro"
          />

          <RatingPicker
            label="Difficulty (1-5)"
            value={difficulty}
            onChange={setDifficulty}
          />
          <RatingPicker
            label="Urgency (1-5)"
            value={urgency}
            onChange={setUrgency}
          />

          <Text style={styles.label}>Estimated minutes</Text>
          <TextInput
            style={styles.input}
            value={estimatedMinutes}
            onChangeText={setEstimatedMinutes}
            keyboardType="number-pad"
          />

          <Text style={styles.label}>Category (optional)</Text>
          <TextInput
            style={styles.input}
            value={category}
            onChangeText={setCategory}
            placeholder="e.g. study, health, errand"
          />

          <View style={styles.actionsRow}>
            <TouchableOpacity style={styles.secondaryButton} onPress={onClose}>
              <Text style={styles.secondaryButtonText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={handleSubmit}
            >
              <Text style={styles.primaryButtonText}>Save</Text>
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
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "white",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 20,
  },
  heading: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 12,
  },
  label: {
    fontSize: 13,
    color: "#444",
    marginTop: 10,
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 15,
  },
  fieldGroup: {
    marginTop: 4,
  },
  ratingRow: {
    flexDirection: "row",
    gap: 8,
  },
  ratingButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#ccc",
    alignItems: "center",
    justifyContent: "center",
  },
  ratingButtonSelected: {
    backgroundColor: "#2563eb",
    borderColor: "#2563eb",
  },
  ratingText: {
    color: "#333",
  },
  ratingTextSelected: {
    color: "white",
    fontWeight: "600",
  },
  actionsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 20,
  },
  primaryButton: {
    backgroundColor: "#2563eb",
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 8,
  },
  primaryButtonText: {
    color: "white",
    fontWeight: "600",
  },
  secondaryButton: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 8,
  },
  secondaryButtonText: {
    color: "#444",
  },
});
