const state = {
	questions: [],
	currentIndex: 0,
	answers: {},
	remainingSeconds: 600,
	timerId: null,
	submitting: false
};

const loadingState = document.querySelector('#loading-state');
const errorState = document.querySelector('#error-state');
const quizContent = document.querySelector('#quiz-content');
const resultState = document.querySelector('#result-state');
const questionForm = document.querySelector('#question-form');
const questionText = document.querySelector('#question-text');
const optionsList = document.querySelector('#options-list');
const questionCount = document.querySelector('#question-count');
const answeredCount = document.querySelector('#answered-count');
const progressBar = document.querySelector('#progress-bar');
const progressPercent = document.querySelector('#progress-percent');
const backButton = document.querySelector('#back-button');
const nextButton = document.querySelector('#next-button');
const submitButton = document.querySelector('#submit-button');
const timerBadge = document.querySelector('#timer-badge');
const timerDisplay = document.querySelector('#quiz-timer');
const timerWarning = document.querySelector('#timer-warning');
const usernameForm = document.querySelector('#username-form');
const usernameInput = document.querySelector('#username-input');
const usernameError = document.querySelector('#username-error');

async function startQuiz(event) {
	event.preventDefault();
	usernameError.hidden = true;
	try {
		const response = await fetch('/api/start', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username: usernameInput.value })
		});
		const result = await response.json();
		if (!response.ok) throw new Error(result.error || 'Could not start the quiz.');
		usernameForm.hidden = true;
		loadingState.hidden = false;
		loadQuestions();
	} catch (error) {
		usernameError.textContent = error.message;
		usernameError.hidden = false;
	}
}

async function loadQuestions() {
	try {
		const response = await fetch('/api/questions');
		if (!response.ok) throw new Error('Could not load the quiz.');
		const quiz = await response.json();
		state.questions = quiz.questions;
		state.remainingSeconds = quiz.remaining_seconds;
		if (!state.questions.length) throw new Error('No questions are available yet.');
		loadingState.hidden = true;
		quizContent.hidden = false;
		renderQuestion();
		startTimer();
	} catch (error) {
		loadingState.hidden = true;
		errorState.textContent = error.message;
		errorState.hidden = false;
	}
}

function formatTime(seconds) {
	const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
	const remaining = (seconds % 60).toString().padStart(2, '0');
	return `${minutes}:${remaining}`;
}

function updateTimerDisplay() {
	timerDisplay.textContent = formatTime(state.remainingSeconds);
	const isWarning = state.remainingSeconds <= 60 && state.remainingSeconds > 0;
	timerBadge.classList.toggle('warning', isWarning);
	timerWarning.hidden = !isWarning;
}

function startTimer() {
	updateTimerDisplay();
	if (state.remainingSeconds <= 0) {
		expireQuiz();
		return;
	}
	state.timerId = window.setInterval(() => {
		state.remainingSeconds -= 1;
		updateTimerDisplay();
		if (state.remainingSeconds <= 0) expireQuiz();
	}, 1000);
}

function expireQuiz() {
	if (state.timerId) window.clearInterval(state.timerId);
	state.remainingSeconds = 0;
	updateTimerDisplay();
	optionsList.querySelectorAll('input').forEach((input) => { input.disabled = true; });
	nextButton.disabled = true;
	backButton.disabled = true;
	submitQuiz(true);
}

function renderQuestion() {
	const question = state.questions[state.currentIndex];
	const total = state.questions.length;
	const selectedAnswer = state.answers[question.id];
	const answeredTotal = Object.keys(state.answers).length;
	const progress = Math.round(((state.currentIndex + 1) / total) * 100);

	questionText.textContent = question.text;
	questionCount.textContent = `Question ${state.currentIndex + 1} of ${total}`;
	answeredCount.textContent = `${answeredTotal} answered`;
	progressBar.style.width = `${progress}%`;
	progressPercent.textContent = `${progress}%`;
	backButton.disabled = state.currentIndex === 0;
	nextButton.hidden = state.currentIndex === total - 1;
	submitButton.hidden = state.currentIndex !== total - 1;
	optionsList.innerHTML = '';

	question.options.forEach((option, index) => {
		const optionWrapper = document.createElement('div');
		optionWrapper.className = 'option';
		const inputId = `question-${question.id}-option-${index}`;
		optionWrapper.innerHTML = `
			<input id="${inputId}" type="radio" name="question-${question.id}" value="${option.id}" ${selectedAnswer === option.id ? 'checked' : ''}>
			<label for="${inputId}">
				<span class="option-letter">${String.fromCharCode(65 + index)}</span>
				<span class="option-text"></span>
			</label>`;
		optionWrapper.querySelector('.option-text').textContent = option.text;
		optionWrapper.querySelector('input').addEventListener('change', (event) => {
			state.answers[question.id] = Number(event.target.value);
			updateAnsweredCount();
		});
		optionsList.appendChild(optionWrapper);
	});
}

function updateAnsweredCount() {
	answeredCount.textContent = `${Object.keys(state.answers).length} answered`;
}

function moveQuestion(step) {
	const nextIndex = state.currentIndex + step;
	if (nextIndex >= 0 && nextIndex < state.questions.length) {
		state.currentIndex = nextIndex;
		renderQuestion();
	}
}


async function submitQuiz(isAutomatic = false) {
	if (state.submitting) return;
	state.submitting = true;
	submitButton.disabled = true;
	nextButton.disabled = true;
	backButton.disabled = true;
	submitButton.textContent = 'Submitting...';
	try {
		const response = await fetch('/api/submit', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ answers: state.answers })
		});
		const result = await response.json();
		if (!response.ok) throw new Error(result.error || 'Could not submit the quiz.');
		quizContent.hidden = true;
		resultState.hidden = false;
		document.querySelector('#result-title').textContent = result.score >= result.total / 2 ? 'Nice work.' : 'Good effort.';
		const timeMessage = isAutomatic || result.timed_out ? ' The time limit was reached.' : '';
		document.querySelector('#result-message').textContent = `You scored ${result.score} out of ${result.total}.${timeMessage} Your answers have been saved.`;
		document.querySelector('#result-total').textContent = result.total;
		document.querySelector('#result-correct').textContent = result.correct;
		document.querySelector('#result-incorrect').textContent = result.incorrect;
		document.querySelector('#result-unanswered').textContent = result.unanswered;
		document.querySelector('#result-percentage').textContent = `${result.percentage}%`;
		renderAnswerReview(result.details);
	} catch (error) {
		errorState.textContent = error.message;
		errorState.hidden = false;
		state.submitting = false;
		submitButton.disabled = false;
		nextButton.disabled = false;
		backButton.disabled = state.currentIndex === 0;
		submitButton.textContent = 'Submit quiz →';
	}
}

function renderAnswerReview(details) {
	const review = document.querySelector('#answer-review');
	review.innerHTML = '';
	details.forEach((detail, index) => {
		const item = document.createElement('div');
		const status = detail.is_correct ? 'correct' : 'incorrect';
		const selectedText = detail.selected_answer || 'No answer selected';
		item.className = `review-item ${status}`;
		item.innerHTML = `<span class="review-question">${index + 1}. <span class="review-question-text"></span></span><span class="review-answer"></span>`;
		item.querySelector('.review-question-text').textContent = detail.question;
		item.querySelector('.review-answer').textContent = detail.is_correct
			? `Correct: ${detail.correct_answer}`
			: `Your answer: ${selectedText} | Correct answer: ${detail.correct_answer}`;
		review.appendChild(item);
	});
}

nextButton.addEventListener('click', () => moveQuestion(1));
backButton.addEventListener('click', () => moveQuestion(-1));
questionForm.addEventListener('submit', (event) => {
	event.preventDefault();
	submitQuiz();
});
document.querySelector('#restart-button').addEventListener('click', async () => {
	await fetch('/api/restart', { method: 'POST' });
	window.location.reload();
});

usernameForm.addEventListener('submit', startQuiz);
