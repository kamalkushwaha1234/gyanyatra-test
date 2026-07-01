const ASSESSMENT_ID = (window.ASSESSMENT_ID) || (document.getElementById('assessment_id')?.value) || null;
const ASSESSMENT_LEVEL = (window.ASSESSMENT_LEVEL) || (document.getElementById('assessment_level')?.value) || null;
let STORAGE_KEY; 
const progress_saved_time =2 * 24 * 60 * 60 * 1000;
let start_time = (window.START_TIME) || (document.getElementById('start_time')?.value) || '';
let submissionSucceeded = false;
const SAVE_SHORTCUT_MESSAGE = "Keyboard shortcut available: press Alt + S to save your progress.";


document.addEventListener("keydown", function (event) {

    const isSaveShortcut =
        event.altKey &&
        event.key.toLowerCase() === "s";

    if (!isSaveShortcut) return;

    event.preventDefault();

    const activeSlide = document.querySelector("#assessmentSlides .slide.active");
    if (!activeSlide || activeSlide.id !== "slide2") return;

    collectDraftData();

    const saveButton =
        document.getElementById("saveProgressButtonTop") ||
        document.getElementById("saveProgressButtonBottom");

    if (saveButton) {
        saveButton.focus();
    }
});


function flashMessage(message, type = "info", duration = 4000) {
    const popupMessage = document.getElementById("popupMessage");
    const modalElement = document.getElementById("alertModal");

    if (popupMessage && modalElement && window.bootstrap) {
        popupMessage.textContent = message;
        popupMessage.classList.remove("text-danger", "text-success");
        if (type === "error") {
            popupMessage.classList.add("text-danger");
        } else if (type === "success") {
            popupMessage.classList.add("text-success");
        }
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
        setTimeout(() => modal.hide(), duration);
        return;
    }

    alert(message);
}

const storage = {
    set: (key, value) => {
        if (!key) return false;
        try {
            const serializedValue = JSON.stringify(value);
            localStorage.setItem(key, serializedValue);
            return true;
        } catch (error) {
            if (error && error.name === "QuotaExceededError") {
                flashMessage("Storage limit reached. Please clear browser data and try again.", "error");
            } else {
                flashMessage("Unable to save draft data in browser storage.", "error");
                console.error("Storage serialization failed:", error);
            }
            return false;
        }
    },
    get: (key) => {
        if (!key) return null;
        try {
            const savedData = localStorage.getItem(key);
            if (!savedData) {
                return null;
            }
            return JSON.parse(savedData);
        } catch (error) {
            flashMessage("Saved draft is corrupted and cannot be restored.", "error");
            console.error("Failed to parse data from localStorage:", error);
            try {
                localStorage.removeItem(key);
            } catch (removeError) {
                console.error("Failed to remove invalid storage key:", removeError);
            }
            return null;
        }
    },
    remove: (key) => {
        if (!key) return;
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error("Failed to remove localStorage key:", error);
        }
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const nextSlideBtn = document.getElementById('nextSlide');
    if (!nextSlideBtn) {
        console.error('nextSlide button not found in DOM');
        return;
    }

    nextSlideBtn.addEventListener('click', function () {
        const requiredInputs = document.querySelectorAll('#assessmentSlides .slide.active [required]');
    let allFilled = true;
    requiredInputs.forEach(input => {
        if (!input.value) {
            input.classList.add('is-invalid');    
            allFilled = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    if (!allFilled) {
        alert("Please fill all required fields before proceeding.");
    }
    if (!allFilled) return;

    const slides = document.querySelectorAll('#assessmentSlides .slide');
    slides[0].style.display = 'none';
    slides[0].classList.remove('active');
    slides[1].style.display = 'block';
    slides[1].classList.add('active');

    const userEmail = document.querySelector("input[name='email']").value || "";

    STORAGE_KEY = `assessment_draft_${ASSESSMENT_ID}_${userEmail}`
    
    restoreDraft();
    flashMessage(SAVE_SHORTCUT_MESSAGE, "info", 20000);

});
});

window.addEventListener("load", function () {
    const startTimeInput = document.getElementById("start_time");

    if (!start_time || start_time.trim() === "") {
        let now = new Date().toLocaleString("en-US", {
        month: "long",
        day: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
    });
    now = now.replace(" at ", " ");
    startTimeInput.value = now;
    } 
});

document.addEventListener("DOMContentLoaded", function () {
    const fieldsets = document.querySelectorAll('form fieldset');
    // Update total number of questions
    const noofquestionid = document.getElementById("noofquestion");
    if (noofquestionid) {
        const span = noofquestionid.querySelector('h2 > span');
        span.textContent = `${fieldsets.length}`;
    }
    fieldsets.forEach((fieldset, index) => {
        fieldset.setAttribute('data-question-id', index + 1);
    const legend = fieldset.querySelector('legend');
    if (legend) {
        legend.id = `Question${index + 1}`;
    }
        const span = fieldset.querySelector('h4 > span.fs-6.fw-normal');
        if (span) {
            span.textContent = `Q${index + 1}.`;
        }   
    const inputElements = fieldset.querySelectorAll('input');
        if (inputElements.length > 0) {
            inputElements.forEach((inputElement) => {
            const oldLabel = inputElement.getAttribute('aria-label');
            if (oldLabel) {
            const totalBlanks = inputElements.length;
            // Replace only the question number part
            const newLabel = oldLabel.replace(/in question\s*\d+/, `of ${totalBlanks} in question ${index + 1}`);
            inputElement.setAttribute('aria-label', newLabel);
            }
            });
}

});
});
    function addBlankSpans() {
        // Select all elements containing sentences
        var sentenceElements = document.querySelectorAll('.if-fill-in-blank');

        // Loop through each sentence element
        sentenceElements.forEach(function(sentenceElement) {
            // Get the sentence text
            var sentenceText = sentenceElement.textContent;

            // Create a new HTML string with blank spans
            var htmlWithHiddenBlanks = sentenceText.replace(/_______+/g, function(match) {
                var blankSpans = '<span class="hidden-text">blank</span>';
                return match + blankSpans;
            });


            // Set the inner HTML of the element to include the blank spans
            sentenceElement.innerHTML = htmlWithHiddenBlanks;
        });
    }
    addBlankSpans();

    document.addEventListener("DOMContentLoaded", function () {
        const textareas = document.querySelectorAll("textarea[data-max-words]");

        textareas.forEach(textarea => {
            const maxWords = parseInt(textarea.dataset.maxWords);
            const msgBox = document.getElementById("msg_" + textarea.id.split("aq_")[1]);

            textarea.addEventListener("input", () => {
                const words = textarea.value.trim().split(/\s+/).filter(Boolean); // Ignore empty strings
                const currentWordCount = words.length;

                if (currentWordCount > maxWords) {
                    textarea.value = words.slice(0, maxWords).join(" ");
                    msgBox.innerText = `You can only enter up to ${maxWords} words. Extra words have been removed.`;
                    msgBox.classList.add("text-danger");
                } else {
                    msgBox.innerText = `Words used: ${currentWordCount}/${maxWords}`;
                    msgBox.classList.remove("text-danger");
                }
            });
        });
    });
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.querySelector('form');
        if (!form) {
            console.error('Form not found in the DOM');
            return;
        }
    
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            const form = this; 
            const submitButton = form.querySelector('button[type="submit"]'); 
            submitButton.disabled = true; // Prevent multiple clicks

            let collectedAnswers = [];
            let attemptedCount = 0;
            let firstUnansweredQuestionId = null;

            // Single-pass: validate answers and collect payload together.
            const allFieldsets = document.querySelectorAll("fieldset");
            allFieldsets.forEach(fieldset => {
                if (fieldset.classList.contains("mcq-question")) {
                    const selected = fieldset.querySelector("input[type='radio']:checked");
                    if (!selected) {
                        if (!firstUnansweredQuestionId) {
                            firstUnansweredQuestionId = fieldset.getAttribute('data-question-id');
                        }
                        return;
                    }

                    collectedAnswers.push({
                        type: "mcq",
                        id: parseInt(selected.name.replace("question", "")),
                        selected_option: parseInt(selected.value)
                    });
                    attemptedCount++;
                    return;
                }

                if (fieldset.classList.contains("fillup-question")) {
                    const qid = parseInt(fieldset.getAttribute("data-fillup-id"));
                    let answersObj = {};
                    let allFilled = true;

                    fieldset.querySelectorAll("input[type='text']").forEach(inputEl => {
                        const blankIndex = inputEl.name.split("_").pop();
                        if (inputEl.value.trim() === "") {
                            allFilled = false;
                        }
                        answersObj["Blank" + blankIndex] = inputEl.value;
                    });

                    if (!allFilled) {
                        if (!firstUnansweredQuestionId) {
                            firstUnansweredQuestionId = fieldset.getAttribute('data-question-id');
                        }
                        return;
                    }

                    collectedAnswers.push({
                        type: "fillup",
                        id: qid,
                        answers: answersObj
                    });
                    attemptedCount++;
                    return;
                }

                if (fieldset.classList.contains("audio-question")) {
                    const qid = parseInt(fieldset.getAttribute("data-audio-id"));
                    const textarea = fieldset.querySelector("textarea");
                    const answerText = textarea ? textarea.value.trim() : "";

                    if (!answerText) {
                        if (!firstUnansweredQuestionId) {
                            firstUnansweredQuestionId = fieldset.getAttribute('data-question-id');
                        }
                        return;
                    }

                    collectedAnswers.push({
                        type: "audio",
                        id: qid,
                        audio_answer: answerText,
                    });
                    attemptedCount++;
                }
            });

            const allAnswered = !firstUnansweredQuestionId;

            if (!allAnswered) {
                var popupMessage = document.getElementById('popupMessage');
                popupMessage.textContent = `Please answer Question Number ${firstUnansweredQuestionId} before proceeding.`;

                // Open Bootstrap Modal
                var modal = new bootstrap.Modal(document.getElementById('alertModal'));
                //In edit mode when hit submit button, if any unanswered question the focus should go to that question
                modal._element.addEventListener('hide.bs.modal', function () {
                // Move focus away from modal before it is hidden
                document.activeElement.blur();
                document.body.focus();
                });
                
                modal._element.addEventListener('hidden.bs.modal', function() {
                    if (firstUnansweredQuestionId) {
                        const question = document.getElementById(`Question${firstUnansweredQuestionId}`);
                        if (question) {
                            // Scroll the fieldset into view
                            const fieldset = question.closest('fieldset');
                            if (fieldset) {
                                fieldset.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                // Highlight the question
                                question.classList.add('highlight-question');

                                // Remove highlight after 10 seconds
                                setTimeout(() => {
                                    question.classList.remove('highlight-question');
                                }, 1000);
                
                                const firstInput = fieldset.querySelector('input[type="radio"], input[type="text"], textarea');
                                if (firstInput) {
                                    setTimeout(() => {
                                        firstInput.setAttribute('tabindex', '-1');
                                        firstInput.focus();
                                    }, 100);
                                } else {
                                    setTimeout(() => {
                                        question.setAttribute('tabindex', '-1'); 
                                        question.focus();
                                    }, 100);
                                }
                            }
                        }
                    }
                }, { once: true });
                // Re-enable submit button 
                submitButton.disabled = false;

                modal.show();
                setTimeout(function() {
                    modal.hide();
                }, 10000);
            }
            else {
                const userName = document.querySelector("input[name='name']").value || "";
                const userEmail = document.querySelector("input[name='email']").value || "";
                const userEdu = document.querySelector("select[name='edu']").value || "";
                const userOrg = document.querySelector("select[name='organization']").value || "";
                const userDisability = document.querySelector("select[name='disability']").value || "";
                const userStartTime = document.querySelector("input[name='start_time']").value || "";

                const finalPayload = {
                    name: userName,
                    email: userEmail,
                    education: userEdu,
                    organization: userOrg,
                    disability: userDisability,
                    start_time: userStartTime,
                    answers: collectedAnswers,
                    attempted_count: attemptedCount
                };

                //console.log("FINAL JSON SENT: ", finalPayload);

                
                // Add hidden input with JSON
                let hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = "answers_json";
                hidden.value = JSON.stringify(finalPayload);
                this.appendChild(hidden);



                // Show a submission modal/message
                const popupMessage = document.getElementById('popupMessage');
                popupMessage.textContent = "Your assessment submission is in progress. Kindly wait while we process your answers...";

                const modal = new bootstrap.Modal(document.getElementById('alertModal'));
                modal.show();

                // Get CSRF token from form
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
                
                // Check if CSRF token is available
                if (!csrfToken) {
                    modal.hide();
                    collectDraftData(); // Save progress before showing error
                    flashMessage(
                        "Security error: Unable to retrieve the authentication token. This may occur if cookies are disabled or blocked in your browser. Please enable cookies and try again, or refresh the page and resubmit. Your progress has been saved.",
                        "error",
                        6000
                    );
                    submitButton.disabled = false;
                    console.error("CSRF token not found in form. availableElements:", document.querySelectorAll('[name=csrfmiddlewaretoken]').length);
                    return;
                }
                
                fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => response.json())
                .then(data => {
                    modal.hide();
                    if (data.success) {
                        storage.remove(STORAGE_KEY);
                        if (data.result_id){
                            goToResultPage(data.result_id);
                        }
                        goToJobPage(data.job_id);
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => {
                    modal.hide();
                    alert("An error occurred while submitting your assessment. Please try again.");
                    console.error("Submission error:", error);
                });
                
            }

        });
    });

 // Sort option sequence when assessment level EQ
document.addEventListener("DOMContentLoaded", function () {
    if (ASSESSMENT_LEVEL === "LS1EIQ1") {
        const mcqFieldsets = document.querySelectorAll(".mcq-question");
        mcqFieldsets.forEach(fieldset => {
            const options = Array.from(fieldset.querySelectorAll("div.d-flex.flex-row.gap-2"));
            //first check all option are ingeter or not
            const allOptionsAreIntegers = options.every(option => {
                const firstChar = option.textContent.trim().toUpperCase()[0];
                return !isNaN(parseInt(firstChar));
            });
            options.sort((a, b) => {
                const optionA = parseInt(a.textContent.trim().toUpperCase()[0].charCodeAt(0));
                const optionB = parseInt(b.textContent.trim().toUpperCase()[0].charCodeAt(0));
                return optionA - optionB;
            });
            const optionsContainer = fieldset.querySelector("div.d-flex.flex-column");
            optionsContainer.innerHTML = "";
            options.forEach(option => optionsContainer.appendChild(option));
        });
    }
});


function goToResultPage(resultId) {
    if (resultId) {
        submissionSucceeded = true;
        window.location.href = `/result-page/${resultId}/`
    }
}

function goToJobPage(jobId) {
    if (jobId) {
        submissionSucceeded = true;
        window.location.href = `/assessment-job/${jobId}/`;
    }
}


function hasDraftableAssessmentData() {
    const activeSlide = document.querySelector("#assessmentSlides .slide.active");
    if (!activeSlide || activeSlide.id !== "slide2") return false;

    const hasMcqSelection = document.querySelector("fieldset.mcq-question input[type='radio']:checked");
    if (hasMcqSelection) return true;

    const hasFillupAnswer = Array.from(
        document.querySelectorAll("fieldset.fillup-question input[type='text']")
    ).some((input) => input.value.trim() !== "");
    if (hasFillupAnswer) return true;

    const hasAudioAnswer = Array.from(
        document.querySelectorAll("fieldset.audio-question textarea")
    ).some((textarea) => textarea.value.trim() !== "");

    return hasAudioAnswer;
}


function collectDraftData() {
    if (!STORAGE_KEY) {
        flashMessage("Please click Next before saving your progress.", "error");
        return;
    }



    let createdAt = Date.now();
    const data = {
        created_at: createdAt,
        answers: []
    };

    document.querySelectorAll("fieldset").forEach(fieldset => {

        if (fieldset.classList.contains("mcq-question")) {
            const checked = fieldset.querySelector("input[type='radio']:checked");
            if (checked) {
                data.answers.push({
                    type: "mcq",
                    qid: checked.name,
                    value: checked.value
                });
            }
        }

        if (fieldset.classList.contains("fillup-question")) {
            const qid = fieldset.dataset.fillupId;
            let blanks = {};
            fieldset.querySelectorAll("input[type='text']").forEach(input => {
                blanks[input.name] = input.value;
            });
            data.answers.push({ type: "fillup", qid, blanks });
        }

        if (fieldset.classList.contains("audio-question")) {
            const qid = fieldset.dataset.audioId;
            const textarea = fieldset.querySelector("textarea");
            if (textarea) {
                data.answers.push({
                    type: "audio",
                    qid,
                    value: textarea.value
                });
            }
        }
    });

    const isSaved = storage.set(STORAGE_KEY, data);
    if (isSaved) {
        flashMessage("Your assessment progress has been saved.", "success");
    }
}


function restoreDraft() {
    const data = storage.get(STORAGE_KEY);
    if (!data) return;

    const now = Date.now();

    // check
    if (now - data.created_at > progress_saved_time) {
        storage.remove(STORAGE_KEY);
        return;
    }
    // Ask user
    const shouldRestore = confirm(
        "We found your saved assessment progress.\n\nDo you want to restore it?"
    );

    if (!shouldRestore) {
        // User declined → delete draft
        storage.remove(STORAGE_KEY);
        return;
    }


    data.answers.forEach(ans => {
        if (ans.type === "mcq") {
            const radio = document.querySelector(
                `input[name="${ans.qid}"][value="${ans.value}"]`
            );
            if (radio) radio.checked = true;
        }

        if (ans.type === "fillup") {
            Object.entries(ans.blanks).forEach(([name, val]) => {
                const input = document.querySelector(`input[name="${name}"]`);
                if (input) input.value = val;
            });
        }

        if (ans.type === "audio") {
            const textarea = document.querySelector(`textarea[name="aq_${ans.qid}"]`);
            if (textarea) textarea.value = ans.value;
        }
    });

    flashMessage("Your previous assessment progress has been restored.", "success");
}


window.addEventListener("offline", () => {
    collectDraftData();
    alert("You're offline right now. Don’t worry—your progress is saved. Submit your assessment once you're back online.");
});

window.addEventListener("online", () => {
    alert("Internet connection restored. You may continue or submit.");
});

function clearExpiredDraft() {
    const data = storage.get(STORAGE_KEY);
    if (!data) return;

    const now = Date.now();
    if (!data.created_at || now - data.created_at > progress_saved_time) {
        storage.remove(STORAGE_KEY);
        console.log("Expired assessment draft removed");
    }
}

window.addEventListener("load", clearExpiredDraft);

window.onbeforeunload = function (event) {
    if (submissionSucceeded) return undefined;
    if (!hasDraftableAssessmentData()) return undefined;

    collectDraftData();
    event.preventDefault();
    return "";
};

