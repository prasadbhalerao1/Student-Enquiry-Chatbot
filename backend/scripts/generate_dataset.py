"""Generate the synthetic CSBS dataset into data/synthetic/.

Everything here is FICTIONAL demonstration data. Names are assembled from name
pools, emails use the reserved `.invalid` TLD (RFC 2606) so they can never
resolve, and the RNG is seeded so repeated runs produce byte-identical files.

    python scripts/generate_dataset.py
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20253
REFERENCE_DATE = date(2026, 4, 15)  # "today" for assignment status generation
N_STUDENTS = 250
DIVISIONS = ["A", "B", "C"]
DEPARTMENT = "Computer Science and Business Systems"
EMAIL_DOMAIN = "csbs-demo.invalid"

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"

# --- Subject catalogue: exactly 12, codes preserved verbatim -----------------
SUBJECTS = [
    ("ARM3201L", "Robotics and its Applications Laboratory", "Lab", "SUJIN ACHANKUNJU PANIKKASSERI"),
    ("ARM3201T", "Robotics and its Applications", "Theory", "Aarrjun Shrikrishna Umrikar"),
    ("CB3201L", "Computer Networks Lab", "Lab", "MAHESH KANTHALE"),
    ("CB3201T", "Computer Networks", "Theory", "MAHESH KANTHALE"),
    ("CB3202L", "Machine Learning Laboratory", "Lab", "NEERAJ SATHAWANE"),
    ("CB3202T", "Machine Learning", "Theory", "NEERAJ SATHAWANE"),
    ("CB3203L-A", "Artificial Intelligence Lab", "Lab", "SUMEDHA RAUT"),
    ("CB3203T-A", "Artificial Intelligence", "Theory", "SUMEDHA RAUT"),
    ("CB3204L", "Skill Development Lab - II", "Lab", "RUTUJA S BACCHAV"),
    ("CB3205L", "Seminar and Technical Communication", "Lab", "Kavita Manojkumar Patil"),
    ("CB3206L", "Business Communication and Value Science-IV", "Lab", "SUHASINI BHAT"),
    ("HSO3203T-F", "Innovation, Business Models and Entrepreneurship", "Theory", "SUMEDHA RAUT"),
]

# Fictional first/last names used to compose student records.
FIRST_NAMES = [
    "Aarav", "Aditi", "Advait", "Ananya", "Anirudh", "Anushka", "Arjun", "Avani",
    "Bhavesh", "Chaitanya", "Darshan", "Deepika", "Dhruv", "Esha", "Gaurav",
    "Harshita", "Hrishikesh", "Ira", "Ishaan", "Janhavi", "Kabir", "Kalyani",
    "Karthik", "Kavya", "Kunal", "Lavanya", "Madhav", "Mahika", "Manav", "Meera",
    "Mihir", "Naina", "Neel", "Nikhil", "Nisha", "Om", "Parth", "Pooja",
    "Pranav", "Prisha", "Rahul", "Raj", "Rhea", "Riya", "Rohan", "Rudra",
    "Saanvi", "Sahil", "Samarth", "Sanjana", "Sarthak", "Shaurya", "Shreya",
    "Siddharth", "Simran", "Tanvi", "Tanmay", "Tara", "Uday", "Vaishnavi",
    "Varun", "Vedant", "Vihaan", "Yash", "Zara", "Aryan", "Devika", "Girish",
    "Hemant", "Indira", "Jatin", "Komal", "Lalit", "Mitali", "Nandini",
]
LAST_NAMES = [
    "Agarwal", "Bhandari", "Chavan", "Deshmukh", "Engineer", "Fernandes",
    "Gokhale", "Hegde", "Iyer", "Joshi", "Kulkarni", "Lokhande", "Mehta",
    "Nadkarni", "Oak", "Pawar", "Qureshi", "Rane", "Sapkal", "Thakur",
    "Upadhyay", "Vaidya", "Wagh", "Yadav", "Zaveri", "Bhosale", "Chitnis",
    "Dalvi", "Gadre", "Inamdar", "Kamat", "Mhatre", "Nene", "Phadke",
    "Ranade", "Salvi", "Tendulkar", "Vartak",
]

SKILL_POOL = [
    "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js",
    "SQL", "PostgreSQL", "MongoDB", "Docker", "Kubernetes", "AWS", "Git",
    "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "Power BI", "Tableau",
    "Figma", "Linux", "REST APIs", "Spring Boot", "Flutter", "Arduino", "ROS",
]
INTEREST_POOL = [
    "Machine Learning", "Web Development", "Data Analytics", "Robotics",
    "Cloud Computing", "Cybersecurity", "UI/UX Design", "Competitive Programming",
    "Entrepreneurship", "Product Management", "IoT", "Computer Vision",
    "Natural Language Processing", "Fintech", "Open Source", "Game Development",
    "Business Analytics", "DevOps",
]

ACTIVITIES = [
    ("ACT001", "CSBS Coding Club", "Technical Club", "Weekly problem-solving and peer code review sessions."),
    ("ACT002", "InnovateHack 24-Hour Hackathon", "Hackathon", "Campus-wide overnight product build competition."),
    ("ACT003", "National Collegiate Hackathon", "Hackathon", "Inter-college hackathon on applied AI themes."),
    ("ACT004", "Weekly Competitive Programming Ladder", "Coding Competition", "Rated contest ladder run by the department."),
    ("ACT005", "DataSprint Analytics Challenge", "Coding Competition", "Dataset modelling contest judged on held-out scores."),
    ("ACT006", "Cloud Fundamentals Workshop", "Workshop", "Hands-on workshop covering cloud deployment basics."),
    ("ACT007", "Robotics Build Workshop", "Workshop", "Microcontroller and actuator prototyping sessions."),
    ("ACT008", "Industry Seminar Series", "Seminar", "Guest lectures from visiting industry practitioners."),
    ("ACT009", "Research Paper Reading Group", "Seminar", "Fortnightly discussion of recent conference papers."),
    ("ACT010", "Inter-Department Cricket Tournament", "Sports", "Annual inter-department cricket fixture."),
    ("ACT011", "Campus Athletics Meet", "Sports", "Track and field events across the institute."),
    ("ACT012", "Basketball Institute League", "Sports", "Season-long institute basketball league."),
    ("ACT013", "Rural Digital Literacy Drive", "Volunteering", "Volunteer-led basic computer literacy sessions."),
    ("ACT014", "Blood Donation Camp", "Volunteering", "Organising and assisting the campus donation camp."),
    ("ACT015", "Campus Sustainability Initiative", "Volunteering", "Waste segregation and plantation activities."),
    ("ACT016", "Annual Cultural Festival", "Cultural", "Multi-day institute cultural festival."),
    ("ACT017", "Dramatics Society Production", "Cultural", "Student-written and student-performed stage production."),
    ("ACT018", "Music and Battle of Bands", "Cultural", "Inter-college band and solo music competition."),
    ("ACT019", "Final Year Project Exhibition", "Project Exhibition", "Public demonstration of student project work."),
    ("ACT020", "Technical Poster Presentation", "Project Exhibition", "Poster session on ongoing technical work."),
    ("ACT021", "Student Council Representation", "Student Leadership", "Elected representation on the student council."),
    ("ACT022", "Class Representative Duties", "Student Leadership", "Liaison between the class and faculty members."),
    ("ACT023", "Technical Fest Organising Committee", "Student Leadership", "Coordinating logistics for the annual technical fest."),
    ("ACT024", "Entrepreneurship Cell", "Technical Club", "Startup mentoring, pitch practice and demo days."),
    ("ACT025", "Open Source Contribution Program", "Technical Club", "Mentored contributions to open source projects."),
]

# Assessment plan per subject type: (title, type, max_marks, weightage)
THEORY_ASSESSMENTS = [
    ("Internal Examination I", "Internal Exam", 30, 0.3),
    ("Internal Examination II", "Internal Exam", 30, 0.3),
    ("Unit Quiz", "Quiz", 10, 0.1),
    ("Technical Assignment", "Technical Assignment", 20, 0.2),
    ("Course Project", "Project", 20, 0.1),
]
LAB_ASSESSMENTS = [
    ("Practical Evaluation I", "Practical Evaluation", 25, 0.3),
    ("Practical Evaluation II", "Practical Evaluation", 25, 0.3),
    ("Lab Continuous Assessment", "Lab Assessment", 20, 0.2),
    ("Mini Project Demonstration", "Project", 25, 0.1),
    ("Seminar Presentation", "Seminar", 10, 0.1),
]

ASSIGNMENT_TITLES = {
    "Theory": [
        ("Problem Set {n}", "Worked problem set covering the current unit."),
        ("Case Study Analysis {n}", "Short written analysis of a supplied case study."),
        ("Implementation Exercise {n}", "Small implementation task with a written summary."),
    ],
    "Lab": [
        ("Lab Record Submission {n}", "Consolidated write-up of completed lab exercises."),
        ("Practical Exercise {n}", "Guided practical task completed outside lab hours."),
        ("Mini Task {n}", "Short applied task building on the lab sessions."),
    ],
}


def _slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ").replace(" ", ".")


def _write_csv(filename: str, header: list[str], rows: list[list]) -> None:
    path = OUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {filename:<34} {len(rows):>6} rows")


def build_teachers() -> tuple[list[list], list[list]]:
    """Return (teacher rows, teacher_subject rows), one teacher per distinct name."""
    seen: dict[str, str] = {}
    teachers: list[list] = []
    for code, _name, _type, faculty in SUBJECTS:
        if faculty not in seen:
            tid = f"TCH{len(seen) + 1:03d}"
            seen[faculty] = tid
    # Deterministic ordering by teacher id.
    ordered = sorted(seen.items(), key=lambda kv: kv[1])
    for faculty, tid in ordered:
        # The first teacher additionally acts as the department coordinator so the
        # extra-scope role is demonstrable.
        is_coord = tid == "TCH001"
        teachers.append([
            tid,
            faculty,
            DEPARTMENT,
            "Professor" if is_coord else "Assistant Professor",
            f"{_slug(faculty)}@{EMAIL_DOMAIN}",
            "true" if is_coord else "false",
        ])

    links = []
    for idx, (code, _n, _t, faculty) in enumerate(SUBJECTS, start=1):
        links.append([f"TS{idx:03d}", seen[faculty], code])
    return teachers, links


def build_students(rng: random.Random) -> list[list]:
    rows = []
    used_names: set[str] = set()
    for i in range(1, N_STUDENTS + 1):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        sid = f"STU{i:04d}"
        division = DIVISIONS[(i - 1) % len(DIVISIONS)]
        roll = f"CSBS3{division}{(i - 1) // len(DIVISIONS) + 1:03d}"
        skills = "; ".join(rng.sample(SKILL_POOL, rng.randint(3, 6)))
        interests = "; ".join(rng.sample(INTEREST_POOL, rng.randint(2, 4)))
        email = f"{sid.lower()}@{EMAIL_DOMAIN}"
        rows.append([sid, name, roll, DEPARTMENT, 3, 6, division, email, skills, interests])
    return rows


def build_attendance(rng: random.Random, students: list[list]) -> list[list]:
    """One row per student-subject pair, with a per-student attendance tendency.

    Each student gets a latent "diligence" value so their attendance correlates
    across subjects (realistic), while per-subject noise keeps it varied. The
    cohort is deliberately shaped to include excellent, average, borderline and
    low cases so every analytic has data to find.
    """
    # Conducted classes differ per subject (labs meet less often than theory).
    conducted_by_subject = {}
    for code, _n, stype, _f in SUBJECTS:
        conducted_by_subject[code] = rng.randint(22, 30) if stype == "Lab" else rng.randint(38, 52)

    # Latent diligence per student, spread across bands.
    diligence: dict[str, float] = {}
    for idx, s in enumerate(students):
        sid = s[0]
        bucket = idx % 20
        if bucket < 1:       # ~5% severe low attendance
            diligence[sid] = rng.uniform(0.35, 0.52)
        elif bucket < 4:     # ~15% below threshold
            diligence[sid] = rng.uniform(0.55, 0.72)
        elif bucket < 7:     # ~15% borderline around 75
            diligence[sid] = rng.uniform(0.72, 0.80)
        elif bucket < 15:    # ~40% comfortable
            diligence[sid] = rng.uniform(0.80, 0.90)
        else:                # ~25% excellent
            diligence[sid] = rng.uniform(0.90, 0.99)

    rows = []
    for s in students:
        sid = s[0]
        base = diligence[sid]
        for code, _n, _t, _f in SUBJECTS:
            conducted = conducted_by_subject[code]
            rate = min(1.0, max(0.0, rng.gauss(base, 0.07)))
            attended = round(conducted * rate)
            attended = max(0, min(conducted, attended))
            rows.append([sid, code, conducted, attended])
    return rows


def build_assessments(rng: random.Random) -> list[list]:
    rows = []
    counter = 1
    for code, _n, stype, _f in SUBJECTS:
        plan = LAB_ASSESSMENTS if stype == "Lab" else THEORY_ASSESSMENTS
        for offset, (title, atype, max_marks, weight) in enumerate(plan):
            adate = date(2026, 1, 20) + timedelta(days=18 * offset + rng.randint(0, 5))
            rows.append([
                f"ASM{counter:04d}", code, title, atype, max_marks,
                adate.isoformat(), weight,
            ])
            counter += 1
    return rows


def build_grades(
    rng: random.Random, students: list[list], assessments: list[list]
) -> list[list]:
    """Per-student results. Missing evaluations are blank, which is NOT zero."""
    # Latent academic ability per student, independent of attendance diligence.
    ability: dict[str, float] = {}
    for idx, s in enumerate(students):
        bucket = idx % 10
        if bucket < 2:
            ability[s[0]] = rng.uniform(0.38, 0.55)   # needs support
        elif bucket < 6:
            ability[s[0]] = rng.uniform(0.55, 0.72)   # average
        elif bucket < 9:
            ability[s[0]] = rng.uniform(0.72, 0.86)   # strong
        else:
            ability[s[0]] = rng.uniform(0.86, 0.98)   # top performers

    rows = []
    for asm in assessments:
        asm_id, _code, _title, _atype, max_marks = asm[0], asm[1], asm[2], asm[3], asm[4]
        for s in students:
            sid = s[0]
            roll = rng.random()
            if roll < 0.04:
                # Not yet evaluated -> blank marks, explicitly not absent.
                rows.append([asm_id, sid, "", "false"])
                continue
            if roll < 0.06:
                # Absent for the assessment -> blank marks, flagged absent.
                rows.append([asm_id, sid, "", "true"])
                continue
            if roll < 0.075:
                # Attempted and scored zero. This is a REAL mark of 0 and is
                # deliberately distinct from the blank rows above, so the
                # dataset exercises the missing-vs-zero distinction.
                rows.append([asm_id, sid, 0.0, "false"])
                continue
            frac = min(1.0, max(0.0, rng.gauss(ability[sid], 0.10)))
            marks = round(max_marks * frac, 1)
            marks = max(0.0, min(float(max_marks), marks))
            rows.append([asm_id, sid, marks, "false"])
    return rows


def build_assignments(rng: random.Random) -> list[list]:
    rows = []
    counter = 1
    for code, _n, stype, _f in SUBJECTS:
        templates = ASSIGNMENT_TITLES[stype]
        for n in range(1, 4):  # 3 assignments per subject
            title_t, desc = templates[(n - 1) % len(templates)]
            assigned = date(2026, 2, 2) + timedelta(days=28 * (n - 1) + rng.randint(0, 4))
            due = assigned + timedelta(days=rng.randint(10, 21))
            rows.append([
                f"ASG{counter:04d}", code, title_t.format(n=n), desc,
                assigned.isoformat(), due.isoformat(), rng.choice([10, 15, 20]),
            ])
            counter += 1
    return rows


def build_student_assignments(
    rng: random.Random, students: list[list], assignments: list[list]
) -> list[list]:
    """Submission state per student per assignment, consistent with REFERENCE_DATE.

    An assignment still open (due date in the future) can be pending without
    being overdue. `pending` means nothing handed in; `submitted` means handed in
    but not yet marked; `evaluated` means handed in and marked.
    """
    rows = []
    for asg in assignments:
        asg_id, _code, _title, _desc, assigned_s, due_s, max_marks = asg
        assigned = date.fromisoformat(assigned_s)
        due = date.fromisoformat(due_s)
        past_due = due < REFERENCE_DATE

        for s in students:
            sid = s[0]
            roll = rng.random()

            if not past_due:
                # Still open: most not handed in yet, some early submissions.
                if roll < 0.55:
                    rows.append([asg_id, sid, "pending", "", ""])
                else:
                    sub = assigned + timedelta(
                        days=rng.randint(1, max(1, (REFERENCE_DATE - assigned).days))
                    )
                    rows.append([asg_id, sid, "submitted", sub.isoformat(), ""])
                continue

            # Closed assignment.
            if roll < 0.12:
                # Never handed in -> genuinely overdue.
                rows.append([asg_id, sid, "pending", "", ""])
            elif roll < 0.27:
                # Handed in but not marked yet. NOT the same as missing.
                sub = assigned + timedelta(days=rng.randint(1, (due - assigned).days))
                rows.append([asg_id, sid, "submitted", sub.isoformat(), ""])
            else:
                sub = assigned + timedelta(days=rng.randint(1, (due - assigned).days))
                marks = round(max_marks * min(1.0, max(0.0, rng.gauss(0.74, 0.16))), 1)
                marks = max(0.0, min(float(max_marks), marks))
                rows.append([asg_id, sid, "evaluated", sub.isoformat(), marks])
    return rows


def build_student_activities(rng: random.Random, students: list[list]) -> list[list]:
    """Varied participation: some very active, some occasional, some with none."""
    roles = ["Participant", "Participant", "Participant", "Team Member",
             "Volunteer", "Organiser", "Team Lead", "Coordinator"]
    statuses = ["Completed", "Completed", "Completed", "Ongoing", "Withdrawn"]
    awards = [
        "First Place", "Second Place", "Third Place", "Finalist",
        "Best Design Award", "Honourable Mention", "Certificate of Merit",
    ]

    rows = []
    for idx, s in enumerate(students):
        sid = s[0]
        bucket = idx % 10
        if bucket < 2:
            count = 0            # ~20% with no recorded activity
        elif bucket < 6:
            count = rng.randint(1, 2)
        elif bucket < 9:
            count = rng.randint(3, 4)
        else:
            count = rng.randint(5, 7)

        chosen = rng.sample(ACTIVITIES, min(count, len(ACTIVITIES)))
        for act in chosen:
            pdate = date(2025, 8, 1) + timedelta(days=rng.randint(0, 250))
            role = rng.choice(roles)
            status = rng.choice(statuses)
            # Awards are the exception, not the rule, and only for completed work.
            achievement = ""
            if status == "Completed" and rng.random() < 0.18:
                achievement = rng.choice(awards)
            rows.append([
                act[0], sid, pdate.isoformat(), role, status, achievement,
            ])
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    print(f"Generating synthetic dataset (seed={SEED}, reference date={REFERENCE_DATE})")
    print(f"Output: {OUT_DIR}")

    # Subjects
    _write_csv(
        "subjects.csv",
        ["subject_code", "subject_name", "subject_type", "credits"],
        [[c, n, t, 1 if t == "Lab" else 3] for c, n, t, _f in SUBJECTS],
    )

    # Teachers + assignments
    teachers, teacher_subjects = build_teachers()
    _write_csv(
        "teachers.csv",
        ["teacher_id", "full_name", "department", "designation", "email",
         "is_department_coordinator"],
        teachers,
    )
    _write_csv(
        "teacher_subjects.csv", ["id", "teacher_id", "subject_code"], teacher_subjects
    )

    # Students
    students = build_students(rng)
    _write_csv(
        "students.csv",
        ["student_id", "full_name", "roll_number", "department", "academic_year",
         "semester", "division", "email", "skills", "interests"],
        students,
    )

    # Attendance
    _write_csv(
        "attendance.csv",
        ["student_id", "subject_code", "classes_conducted", "classes_attended"],
        build_attendance(rng, students),
    )

    # Academic
    assessments = build_assessments(rng)
    _write_csv(
        "assessments.csv",
        ["assessment_id", "subject_code", "title", "assessment_type", "max_marks",
         "assessment_date", "weightage"],
        assessments,
    )
    _write_csv(
        "grades.csv",
        ["assessment_id", "student_id", "marks_obtained", "is_absent"],
        build_grades(rng, students, assessments),
    )

    # Assignments
    assignments = build_assignments(rng)
    _write_csv(
        "assignments.csv",
        ["assignment_id", "subject_code", "title", "description", "assigned_date",
         "due_date", "max_marks"],
        assignments,
    )
    _write_csv(
        "student_assignments.csv",
        ["assignment_id", "student_id", "status", "submission_date", "marks_obtained"],
        build_student_assignments(rng, students, assignments),
    )

    # Extracurricular
    _write_csv(
        "extracurricular_activities.csv",
        ["activity_id", "title", "category", "description"],
        [list(a) for a in ACTIVITIES],
    )
    _write_csv(
        "student_activities.csv",
        ["activity_id", "student_id", "participation_date", "role",
         "participation_status", "achievement"],
        build_student_activities(rng, students),
    )

    print("Done. All records are synthetic demonstration data.")


if __name__ == "__main__":
    main()
