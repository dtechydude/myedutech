const url = window.location.href
const quizBox = document.getElementById('quiz-box')
const timerBox = document.getElementById('timer-box')
const quizForm = document.getElementById('quiz-form')
const resultBox = document.getElementById('result-box')
const scoreText = document.getElementById('score-text')

let timer;

const startTimer = (seconds) => {
    let time = seconds;
    timer = setInterval(() => {
        time--;
        if (time <= 0) {
            clearInterval(timer);
            sendData(); // Auto-submit
        }
        let mins = Math.floor(time / 60);
        let secs = time % 60;
        timerBox.innerHTML = `<b>Time Left: ${mins}:${secs < 10 ? '0' : ''}${secs}</b>`;
    }, 1000);
}

// 1. Fetch data
fetch(`${url}data/`)
    .then(res => res.json())
    .then(response => {
        response.data.forEach(q => {
            quizBox.innerHTML += `
                <div class="mb-4">
                    <p class="h5">${q.text}</p>
                    ${q.answers.map(a => `
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="${q.id}" id="${a.id}" value="${a.id}">
                            <label class="form-check-label" for="${a.id}">${a.text}</label>
                        </div>
                    `).join('')}
                </div><hr>`;
        });
        startTimer(response.time * 60);
    });

// 2. Submit data
const sendData = () => {
    const formData = new FormData(quizForm);
    clearInterval(timer);

    fetch(`${url}save/`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        quizForm.classList.add('d-none');
        resultBox.classList.remove('d-none');
        scoreText.innerHTML = data.passed ? 
            `<span class="text-success">Passed! Score: ${data.score}%</span>` : 
            `<span class="text-danger">Failed. Score: ${data.score}%</span>`;
    });
}

quizForm.addEventListener('submit', e => {
    e.preventDefault();
    if (confirm("Are you sure you want to end the exam?")) {
        sendData();
    }
});