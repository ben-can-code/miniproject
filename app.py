from flask import Flask, request, jsonify, render_template
import re
import time

app = Flask(__name__)

# ── In-memory session store (keyed by session_id) ──────────────────────────
sessions = {}

# ── CAT Questions ──────────────────────────────────────────────────────────
CAT_QUESTIONS = [
    {
        "question": "What does NLP stand for?",
        "options": {
            "A": "Natural Language Processing",
            "B": "Neural Learning Program",
            "C": "Numerical Logic Process",
            "D": "Network Language Protocol"
        },
        "hint": "It is the field that helps computers understand human language.",
        "answer": "A"
    },
    {
        "question": "Which language is widely used in NLP?",
        "options": {
            "A": "HTML",
            "B": "Python",
            "C": "CSS",
            "D": "PHP"
        },
        "hint": "It is beginner-friendly and heavily used in AI.",
        "answer": "B"
    },
    {
        "question": "Which Python library is commonly used for NLP?",
        "options": {
            "A": "Bootstrap",
            "B": "React",
            "C": "spaCy",
            "D": "Photoshop"
        },
        "hint": "It processes text and language data.",
        "answer": "C"
    },
    {
        "question": "What is tokenization?",
        "options": {
            "A": "Creating databases",
            "B": "Splitting text into smaller units",
            "C": "Encrypting information",
            "D": "Compressing files"
        },
        "hint": "It breaks sentences into words or tokens.",
        "answer": "B"
    },
    {
        "question": "What is the purpose of a chatbot?",
        "options": {
            "A": "Repair computers",
            "B": "Interact with users automatically",
            "C": "Build networks",
            "D": "Create animations"
        },
        "hint": "It communicates with users through conversations.",
        "answer": "B"
    }
]

# ── NLP Helpers ────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase and strip punctuation for keyword matching."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def detect_greeting(text: str) -> bool:
    greetings = {"hello", "hi", "hey", "good morning", "good afternoon",
                 "good evening", "howdy", "greetings", "sup", "what's up"}
    tokens = set(normalize(text).split())
    # also check full phrase greetings
    norm = normalize(text)
    return bool(tokens & greetings) or any(g in norm for g in greetings)


def detect_exit(text: str) -> bool:
    exits = {"exit", "quit", "bye", "goodbye", "see you", "farewell"}
    norm = normalize(text)
    return any(word in norm.split() or word in norm for word in exits)


def detect_register_intent(text: str) -> bool:
    keywords = {"register", "registration", "sign up", "enroll", "start",
                 "begin", "cat", "quiz", "exam", "examination"}
    tokens = set(normalize(text).split())
    return bool(tokens & keywords)


def extract_answer_choice(text: str) -> str | None:
    """
    Extract a single letter answer (A-D) from user input.
    Accepts: 'A', 'a', 'option a', 'answer is b', 'B.', etc.
    """
    norm = normalize(text)
    # Direct single letter
    match = re.fullmatch(r"[abcd]", norm)
    if match:
        return match.group().upper()
    # Letter at start or after keywords
    match = re.search(r"\b([abcd])\b", norm)
    if match:
        return match.group(1).upper()
    return None


# ── Session helpers ────────────────────────────────────────────────────────

def new_session(session_id: str):
    sessions[session_id] = {
        "state": "greeting",      # greeting | awaiting_name | in_cat | finished
        "name": None,
        "q_index": 0,             # current question (0-based)
        "score": 0,
        "results": [],            # list of {question, user_answer, correct, correct_answer}
        "cat_started": False,
    }


def get_session(session_id: str) -> dict:
    if session_id not in sessions:
        new_session(session_id)
    return sessions[session_id]


def build_question_payload(q_index: int) -> dict:
    """Return the structured question dict for the frontend."""
    q = CAT_QUESTIONS[q_index]
    return {
        "type": "question",
        "number": q_index + 1,
        "total": len(CAT_QUESTIONS),
        "question": q["question"],
        "options": q["options"],
        "hint": q["hint"]
    }


def build_review(session: dict) -> list[str]:
    lines = []
    for i, r in enumerate(session["results"]):
        status = "✅ Correct" if r["correct"] else f"❌ Wrong (Correct: {r['correct_answer']})"
        lines.append(f"Q{i+1}: {r['question'][:45]}… → {status}")
    return lines


# ── Main chat logic ────────────────────────────────────────────────────────

def process_message(session_id: str, user_input: str) -> list[dict]:
    """
    Returns a list of response message objects:
      { "text": "...", "type": "bot" | "question" | "score" }
    """
    session = get_session(session_id)
    responses = []

    def bot(text, msg_type="bot"):
        responses.append({"text": text, "type": msg_type})

    # ── Exit intent (works from any state) ──────────────────────────────
    if detect_exit(user_input):
        if session["state"] == "in_cat":
            # Mark unanswered questions as wrong
            while session["q_index"] < len(CAT_QUESTIONS):
                q = CAT_QUESTIONS[session["q_index"]]
                session["results"].append({
                    "question": q["question"],
                    "user_answer": "—",
                    "correct": False,
                    "correct_answer": q["answer"]
                })
                session["q_index"] += 1

        score = session["score"]
        total = len(CAT_QUESTIONS)
        bot(f"You scored {score} out of {total}.", "score")
        bot("📋 Review:", "bot")
        for line in build_review(session):
            bot(line, "review")
        bot("Thank you for using the Student Academic Assistant Chatbot. Goodbye! 👋")
        session["state"] = "finished"
        return responses

    # ── State machine ────────────────────────────────────────────────────

    state = session["state"]

    # ── GREETING state ────────────────────────────────────────────────
    if state == "greeting":
        if detect_greeting(user_input):
            bot("Hello! 👋 Welcome to the Student Academic Assistant Chatbot.")
            bot("I'm here to help you with your academic needs.")
            bot("Please register before starting the CAT examination.")
            bot("Type <b>register</b> or <b>start</b> to begin registration.")
            session["state"] = "pre_register"
        elif detect_register_intent(user_input):
            bot("Great! Let's get you registered.")
            bot("Please enter your student name:")
            session["state"] = "awaiting_name"
        else:
            bot("Hi there! 👋 I'm your Student Academic Assistant.")
            bot("Type <b>hello</b> to get started, or <b>register</b> to begin the CAT.")

    # ── PRE-REGISTER: waiting for them to say register/start ──────────
    elif state == "pre_register":
        if detect_register_intent(user_input) or detect_greeting(user_input):
            bot("Great! Let's get you registered.")
            bot("Please enter your <b>student name</b>:")
            session["state"] = "awaiting_name"
        else:
            bot("Please type <b>register</b> or <b>start</b> to begin your registration.")

    # ── AWAITING NAME ─────────────────────────────────────────────────
    elif state == "awaiting_name":
        name = user_input.strip()
        if len(name) < 2:
            bot("That doesn't look like a valid name. Please enter your full name:")
        else:
            session["name"] = name
            bot(f"✅ Registration completed successfully. Welcome, <b>{name}</b>!")
            bot("Your CAT examination will start in 5 seconds…")
            bot("__COUNTDOWN__", "countdown")   # frontend handles countdown
            session["state"] = "cat_countdown"

    # ── CAT COUNTDOWN: frontend fires a follow-up after 5 s ───────────
    elif state == "cat_countdown":
        # This state is triggered by the auto follow-up from frontend
        bot("📝 CAT examination started successfully.")
        session["state"] = "in_cat"
        session["q_index"] = 0
        responses.append(build_question_payload(0))

    # ── IN CAT ───────────────────────────────────────────────────────
    elif state == "in_cat":
        q_index = session["q_index"]
        if q_index >= len(CAT_QUESTIONS):
            # Shouldn't normally land here, but guard anyway
            bot("The CAT has already been completed. Type <b>exit</b> to see your results.")
            return responses

        current_q = CAT_QUESTIONS[q_index]
        choice = extract_answer_choice(user_input)

        if choice is None:
            bot("Please enter a valid answer: <b>A</b>, <b>B</b>, <b>C</b>, or <b>D</b>.")
            return responses

        correct = choice == current_q["answer"]
        if correct:
            session["score"] += 1
            bot(f"✅ Correct! Well done.")
        else:
            bot(f"❌ Incorrect. The correct answer was <b>{current_q['answer']}</b>.")

        session["results"].append({
            "question": current_q["question"],
            "user_answer": choice,
            "correct": correct,
            "correct_answer": current_q["answer"]
        })
        session["q_index"] += 1

        if session["q_index"] < len(CAT_QUESTIONS):
            responses.append(build_question_payload(session["q_index"]))
        else:
            bot("🎉 CAT examination completed!")
            bot(f"You scored <b>{session['score']} out of {len(CAT_QUESTIONS)}</b>.", "score")
            bot("📋 Here's your review:")
            for line in build_review(session):
                bot(line, "review")
            bot("Thank you for using the Student Academic Assistant Chatbot! 🎓")
            session["state"] = "finished"

    # ── FINISHED ──────────────────────────────────────────────────────
    elif state == "finished":
        bot("The session has ended. Please refresh the page to start a new session.")

    return responses


# ── Flask Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "default")
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({"responses": [{"text": "Please type a message.", "type": "bot"}]})

    responses = process_message(session_id, user_input)
    return jsonify({"responses": responses})


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "default")
    new_session(session_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
