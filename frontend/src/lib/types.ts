/** Response shapes mirroring the backend's Pydantic models. */

export interface TeacherProfile {
  teacher_id: string;
  full_name: string;
  email: string;
  department: string;
  designation: string;
  is_department_coordinator: boolean;
  subject_codes: string[];
  attendance_threshold: number;
  threshold_note: string;
  demo_mode: boolean;
}

export interface DemoTeacherOption {
  teacher_id: string;
  full_name: string;
  designation: string;
  department: string;
  is_department_coordinator: boolean;
  subject_codes: string[];
}

export interface Subject {
  subject_code: string;
  subject_name: string;
  subject_type: "Theory" | "Lab";
  credits: number;
  faculty_name: string | null;
  enrolled_students: number;
  class_attendance_percentage: number | null;
  mean_student_attendance_percentage: number | null;
}

export interface AttendanceRow {
  student_id: string;
  full_name: string;
  roll_number: string;
  division: string;
  classes_attended: number;
  classes_conducted: number;
  attendance_percentage: number;
  below_threshold: boolean;
  status: "Below threshold" | "At risk" | "Meeting threshold";
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type PaginatedAttendance = Paginated<AttendanceRow> & {
  threshold: number;
};

export interface SubjectAnalytics {
  subject_code: string;
  subject_name: string | null;
  subject_type: string | null;
  enrolled_students: number;
  classes_conducted: number;
  threshold: number;
  class_attendance_percentage: number | null;
  mean_student_attendance_percentage: number | null;
  students_below_threshold: number;
  students_meeting_threshold: number;
  lowest_percentage: number | null;
  highest_percentage: number | null;
}

export interface DashboardData {
  subject_count: number;
  student_count: number;
  threshold: number;
  subject_attendance: SubjectAnalytics[];
  overall_class_attendance_percentage: number | null;
  overall_mean_student_attendance_percentage: number | null;
  students_below_threshold: number;
  attendance_record_count: number;
  overdue_assignment_count: number;
  pending_evaluation_count: number;
  upcoming_deadlines: {
    assignment_id: string;
    subject_code: string;
    title: string;
    due_date: string;
    days_until_due: number;
  }[];
  recent_activities: {
    title: string;
    category: string;
    participation_date: string;
    student_name: string;
    achievement: string | null;
  }[];
  calculation_notes: Record<string, string>;
}

export interface Assessment {
  assessment_id: string;
  subject_code: string;
  title: string;
  assessment_type: string;
  max_marks: number;
  assessment_date: string;
  weightage: number;
  total_students: number;
  evaluated_count: number;
  pending_evaluation_count: number;
  absent_count: number;
  average_marks: number | null;
  average_percentage: number | null;
}

export interface PerformanceStudent {
  student_id: string;
  full_name: string;
  roll_number: string;
  division: string;
  performance_percentage: number | null;
  evaluated_count: number;
  missing_count: number;
  absent_count: number;
}

export interface PerformanceSummary {
  subject_code: string;
  assessment_count: number;
  students: PerformanceStudent[];
  evaluated_students?: number;
  class_average_percentage: number | null;
  distribution: Record<string, number>;
  calculation_note?: string;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AssignmentSummary {
  assignment_id: string;
  subject_code: string;
  title: string;
  description: string;
  assigned_date: string;
  due_date: string;
  max_marks: number;
  is_past_due: boolean;
  total_students: number;
  pending_count: number;
  submitted_count: number;
  evaluated_count: number;
  overdue_count: number;
  not_yet_due_pending_count: number;
  average_marks: number | null;
}

export interface OverdueRecord {
  student_id: string;
  full_name: string;
  roll_number: string;
  division: string;
  assignment_id: string;
  subject_code: string;
  title: string;
  due_date: string;
  days_overdue: number;
}

export interface Student {
  student_id: string;
  full_name: string;
  roll_number: string;
  division: string;
  academic_year: number;
  semester: number;
  skills: string[];
  interests: string[];
}

export interface StudentAcademicSummary {
  student_id: string;
  full_name: string;
  roll_number: string;
  division: string;
  department: string;
  academic_year: number;
  semester: number;
  skills: string[];
  interests: string[];
  attendance: {
    subject_code: string;
    subject_name: string;
    classes_attended: number;
    classes_conducted: number;
    attendance_percentage: number;
    below_threshold: boolean;
    status: string;
    classes_needed_for_threshold: number;
  }[];
  subjects_below_attendance_threshold: number;
  assessments: {
    subject_code: string;
    title: string;
    assessment_type: string;
    max_marks: number;
    marks_obtained: number | null;
    is_absent: boolean;
    percentage: number | null;
    evaluation_state: "evaluated" | "absent" | "not yet evaluated";
  }[];
  average_assessment_percentage: number | null;
  assessments_not_evaluated: number;
  assignments: {
    assignment_id: string;
    subject_code: string;
    title: string;
    due_date: string;
    max_marks: number;
    status: string;
    submission_date: string | null;
    marks_obtained: number | null;
    is_overdue: boolean;
  }[];
  overdue_assignment_count: number;
  threshold: number;
}

export interface ExtracurricularSummary {
  students_in_scope: number;
  students_with_activities: number;
  students_without_activities: number;
  total_participations: number;
  by_category: Record<string, number>;
  by_role: Record<string, number>;
  achievement_count: number;
  top_activities: { title: string; participants: number }[];
}

export interface StudentActivities {
  student_id: string;
  activity_count: number;
  achievements_recorded: number;
  activities: {
    activity_id: string;
    title: string;
    category: string;
    description: string;
    participation_date: string;
    role: string;
    participation_status: string;
    achievement: string | null;
  }[];
}

export interface ProviderSpec {
  id: string;
  label: string;
  requires_api_key: boolean;
  supports_tool_calling: boolean;
  supports_custom_base_url: boolean;
  default_base_url: string | null;
  suggested_models: string[];
  notes: string;
  api_key_url: string | null;
}

/** BYOK settings. Held in memory only; never written to storage. */
export interface ProviderConfig {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
  temperature?: number;
}

export interface ProviderTestResult {
  ok: boolean;
  message: string;
  model?: string | null;
  provider?: string | null;
  supports_tool_calling?: boolean | null;
  sample?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  error?: string;
  toolCalls?: { name: string; state: string }[];
}
