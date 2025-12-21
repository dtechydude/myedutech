
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
            timerBox.innerHTML = "<b>Time Expired! Submitting...</b>";
            sendData(); 
        }
        let mins = Math.floor(time / 60);
        let secs = time % 60;
        timerBox.innerHTML = `<b>Time Left: ${mins}:${secs < 10 ? '0' : ''}${secs}</b>`;
    }, 1000);
}

// 1. Fetch data from server
fetch(`${url}data/`)
    .then(res => res.json())
    .then(response => {
        if (response.error) {
            alert(response.error);
            window.location.href = '/'; 
            return;
        }

        // Render Questions
        response.data.forEach((q, index) => {
            // Container for each question - uses bg-white for better formula contrast
            let questionContent = `<div class="mb-4 p-3 border rounded shadow-sm bg-white">
                                    <p class="h5"><b>Question ${index + 1}:</b> ${q.text}</p>`;

            // Image Support (Google Drive Links)
            if (q.image) {
                questionContent += `
                    <div class="mb-3 text-center">
                        <img src="${q.image}" class="img-fluid rounded border" style="max-height: 300px;" alt="Question Diagram">
                    </div>`;
            }

            if (q.type === 'MCQ') {
                // Logic for Multiple Choice (A, B, C, D)
                const letters = ['A', 'B', 'C', 'D'];
                letters.forEach(letter => {
                    const optionText = q.options[letter];
                    if (optionText && optionText.trim() !== "") {
                        questionContent += `
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="${q.id}" id="${q.id}-${letter}" value="${letter}">
                                <label class="form-check-label" for="${q.id}-${letter}">
                                    <b>${letter}.</b> ${optionText}
                                </label>
                            </div>`;
                    }
                });
            } else {
                // Logic for Short Answer (Text Input)
                questionContent += `
                    <div class="mt-2">
                        <input type="text" class="form-control" name="${q.id}" placeholder="Type your answer here...">
                    </div>`;
            }

            questionContent += `</div>`;
            quizBox.innerHTML += questionContent;
        });

        // Trigger MathJax to render LaTeX formulas after questions are injected into DOM
        if (window.MathJax) {
            MathJax.typesetPromise().catch((err) => console.log('MathJax error:', err));
        }

        startTimer(response.time_left); 
    })
    .catch(err => console.error("Error loading quiz data:", err));

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
        if (data.error) {
            alert(data.error);
        } else {
            quizForm.classList.add('d-none');
            resultBox.classList.remove('d-none');
            
            let resultsHtml = data.passed ? 
                `<h2 class="text-success text-center">Passed! Score: ${data.score}%</h2>` : 
                `<h2 class="text-danger text-center">Failed. Score: ${data.score}%</h2>`;
            
            scoreText.innerHTML = resultsHtml;
        }
    })
    .catch(err => console.error("Error saving quiz:", err));
}

quizForm.addEventListener('submit', e => {
    e.preventDefault();
    if (confirm("Are you sure you want to end the exam?")) {
        sendData();
    }
});