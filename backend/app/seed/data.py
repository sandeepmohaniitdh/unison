"""Invented departments and courses. Nothing is copied from any real curriculum."""

DEPARTMENTS = [
    ("CSE", "Computer Science and Engineering"),
    ("EE", "Electrical Engineering"),
    ("ME", "Mechanical Engineering"),
    ("MA", "Mathematics"),
    ("PH", "Physics"),
]

# (department code, course code, title)
COURSES = [
    ("CSE", "CS301", "Software Engineering"),
    ("CSE", "CS302", "Database Systems"),
    ("CSE", "CS305", "Computer Networks"),
    ("CSE", "CS310", "Machine Learning Basics"),
    ("EE", "EE201", "Signals and Systems"),
    ("EE", "EE204", "Digital Circuits"),
    ("EE", "EE305", "Power Electronics"),
    ("EE", "EE310", "Embedded Systems Lab"),
    ("ME", "ME201", "Engineering Thermodynamics"),
    ("ME", "ME210", "Fluid Mechanics"),
    ("ME", "ME305", "Design of Machine Elements"),
    ("ME", "ME320", "Robotics Project"),
    ("MA", "MA201", "Linear Algebra"),
    ("MA", "MA205", "Probability and Statistics"),
    ("MA", "MA301", "Numerical Methods"),
    ("MA", "MA310", "Optimisation"),
    ("PH", "PH201", "Classical Mechanics"),
    ("PH", "PH210", "Electromagnetism"),
    ("PH", "PH301", "Quantum Physics"),
    ("PH", "PH320", "Computational Physics"),
]

TERM = "Jul-Nov 2026"

GROUP_RUBRIC = [("Design", 15), ("Implementation", 20), ("Report", 15)]
INDIVIDUAL_RUBRIC = [("Correctness", 10), ("Clarity", 10)]

TEAM_WORDS = [
    "Byte",
    "Pixel",
    "Quantum",
    "Nova",
    "Vector",
    "Delta",
    "Echo",
    "Orbit",
    "Prism",
    "Spark",
    "Cipher",
    "Atlas",
    "Comet",
    "Helix",
    "Matrix",
    "Nimbus",
    "Pulse",
    "Rocket",
    "Sigma",
    "Turbo",
]
TEAM_NOUNS = [
    "Builders",
    "Crew",
    "Squad",
    "Labs",
    "Makers",
    "Minds",
    "Works",
    "Coders",
    "Thinkers",
    "Pioneers",
]

RESOURCE_TITLES = ["Course outline", "Lecture 1 slides", "Lecture 2 notes", "Problem set hints", "Reading list"]

# The people shown in the Figma screens, with demo emails.
DEMO_ADMIN = ("Demo Admin", "demo.admin@example.com")
DEMO_TEACHER = ("Dr. Kavya Menon", "demo.teacher@example.com")
DEMO_STUDENTS = [
    ("Sandeep M", "demo.student@example.com"),
    ("Km Shristi Singh", "shristi.demo@example.com"),
    ("Tirtho Paul", "tirtho.demo@example.com"),
    ("Ujjwal Gupta", "ujjwal.demo@example.com"),
]
DEMO_PASSWORD = "unison-demo"
