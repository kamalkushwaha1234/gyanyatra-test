
const SHOW_SUB_LEVEL =  (window.SHOW_SUB_LEVEL) || (document.getElementById('SHOW_SUB_LEVEL')?.value) || null;
const total_questions = (window.total_questions) || (document.getElementById('total_questions')?.value) || null;
const assessmentlevels =  (window.assessmentlevels) || (document.getElementById('assessmentlevels')?.value) || null;
const subjects =  (window.subjects) || (document.getElementById('subjects')?.value) || null;
const sub_levels =  (window.sub_levels) || (document.getElementById('sub_levels')?.value) || null;
const MAP_SUBLEVELS_TO_SUBJECT =  (window.MAP_SUBLEVELS_TO_SUBJECT) || (document.getElementById('MAP_SUBLEVELS_TO_SUBJECT')?.value) || null;


const questionTypeMeta = {
    text_question: { distKey: "text", countInput: "text_question_count", totalKey: "Questions", label: "text questions" },
    audio_question: { distKey: "audio", countInput: "audio_question_count", totalKey: "Audios", label: "audio questions" },
    fill_in_the_blank: { distKey: "fillup", countInput: "fill_in_the_blank_count", totalKey: "Fillups", label: "fill in the blank questions" },
};

function get_question_count(subject, level, sub_level, type) {
    if (!(subject in total_questions) || !(type in total_questions[subject])) return 0;
    let countQuestion = 0;
    for (const countlevel of total_questions[subject][type]) {
        if (countlevel.level !== level) continue;
        if (!sub_level || countlevel.sub_level === sub_level) {
            countQuestion += countlevel.count || 0;
        }
    }
    return countQuestion;
}

function getSelectedSubjectLabel() {
    const subjectSelect = document.getElementById("subject");
    return subjectSelect.options[subjectSelect.selectedIndex].text;
}

function getSelectedSubjectValue() {
    return document.getElementById("subject").value;
}

function hasSublevelsForSelection() {
    return SHOW_SUB_LEVEL.includes(getSelectedSubjectLabel());
}

function setCountInputsReadOnly(isReadOnly) {
    Object.values(questionTypeMeta).forEach((meta) => {
        const countInput = document.getElementById(meta.countInput);
        if (countInput) countInput.readOnly = isReadOnly;
    });
}

function resetCountValues() {
    Object.values(questionTypeMeta).forEach((meta) => {
        const countInput = document.getElementById(meta.countInput);
        if (countInput) countInput.value = "0";
    });
    document.getElementById("sublevel_distribution_json").value = "";
}

function getCurrentDistributionFromTable() {
    const distribution = { text: {}, audio: {}, fillup: {} };
    document.querySelectorAll(".sublevel-count-input").forEach((input) => {
        const type = input.dataset.type;
        const sub = input.dataset.sublevel;
        const val = parseInt(input.value || "0", 10);
        if (!Number.isNaN(val) && val > 0) distribution[type][sub] = val;
    });
    return distribution;
}

function updateDistributionJsonAndTotals() {
    const hidden = document.getElementById("sublevel_distribution_json");
    const distribution = getCurrentDistributionFromTable();
    hidden.value = JSON.stringify(distribution);

    Object.values(questionTypeMeta).forEach((meta) => {
        const countInput = document.getElementById(meta.countInput);
        const sum = Object.values(distribution[meta.distKey] || {}).reduce((a, b) => a + b, 0);
        if (countInput) countInput.value = sum;
    });
}

function getAvailableSublevels(subjectLabel, subjectValue, level) {
    const mappedSublevels = MAP_SUBLEVELS_TO_SUBJECT[subjectValue] || [];
    return mappedSublevels
        .map(([subValue, subLabel]) => {
            const textAvail = get_question_count(subjectLabel, level, subValue, "Questions");
            const audioAvail = get_question_count(subjectLabel, level, subValue, "Audios");
            const fillupAvail = get_question_count(subjectLabel, level, subValue, "Fillups");
            return { subValue, subLabel, textAvail, audioAvail, fillupAvail };
        })
        .filter((sub) => sub.textAvail > 0 || sub.audioAvail > 0 || sub.fillupAvail > 0);
}

function renderSublevelDistribution(options = {}) {
    const { resetValues = false } = options;
    const section = document.getElementById("sublevel_distribution_section");
    const body = document.getElementById("sublevel_distribution_body");
    const hidden = document.getElementById("sublevel_distribution_json");
    const previous = resetValues ? { text: {}, audio: {}, fillup: {} } : getCurrentDistributionFromTable();
    const subjectLabel = getSelectedSubjectLabel();
    const subjectValue = getSelectedSubjectValue();
    const level = document.getElementById("level").value;

    if (!hasSublevelsForSelection()) {
        section.style.display = "none";
        body.innerHTML = "";
        hidden.value = "";
        setCountInputsReadOnly(false);
        return;
    }

    const availableSublevels = getAvailableSublevels(subjectLabel, subjectValue, level);
    section.style.display = availableSublevels.length ? "block" : "none";
    body.innerHTML = "";
    if (!availableSublevels.length) {
        hidden.value = "";
        resetCountValues();
        setCountInputsReadOnly(true);
        return;
    }

    body.innerHTML = availableSublevels.map((sub) => {
        const prevText = previous.text[sub.subValue] || 0;
        const prevAudio = previous.audio[sub.subValue] || 0;
        const prevFillup = previous.fillup[sub.subValue] || 0;

        return `
            <tr>
                <td>${sub.subLabel}</td>
                <td>
                    <input type="number" min="0" max="${sub.textAvail}" value="${prevText}"
                        class="form-control sublevel-count-input"
                        data-type="text" data-sublevel="${sub.subValue}"
                        ${document.getElementById("text_question").checked ? "" : "disabled"}>
                    <small class="text-muted">Available: ${sub.textAvail}</small>
                </td>
                <td>
                    <input type="number" min="0" max="${sub.audioAvail}" value="${prevAudio}"
                        class="form-control sublevel-count-input"
                        data-type="audio" data-sublevel="${sub.subValue}"
                        ${document.getElementById("audio_question").checked ? "" : "disabled"}>
                    <small class="text-muted">Available: ${sub.audioAvail}</small>
                </td>
                <td>
                    <input type="number" min="0" max="${sub.fillupAvail}" value="${prevFillup}"
                        class="form-control sublevel-count-input"
                        data-type="fillup" data-sublevel="${sub.subValue}"
                        ${document.getElementById("fill_in_the_blank").checked ? "" : "disabled"}>
                    <small class="text-muted">Available: ${sub.fillupAvail}</small>
                </td>
            </tr>
        `;
    }).join("");

    setCountInputsReadOnly(true);
    document.querySelectorAll(".sublevel-count-input").forEach((input) => {
        input.addEventListener("input", () => {
            const max = parseInt(input.max || "0", 10);
            const value = parseInt(input.value || "0", 10);
            if (!Number.isNaN(max) && !Number.isNaN(value) && value > max) input.value = max;
            if (!Number.isNaN(value) && value < 0) input.value = 0;
            updateDistributionJsonAndTotals();
        });
    });
    updateDistributionJsonAndTotals();
}

// function buildQuestionCountsList() {
//     const listContainer = document.getElementById("question-count-list");
//     for (const subjectObj of subjects) {
//         const subject = subjectObj.label;
//         const li = document.createElement("li");
//         li.className = "list-group-item mb-3";
//         li.innerHTML = `<span aria-label="Subject">${subject}</span>`;

//         for (const level of assessmentlevels) {
//             const levelValue = level[0];
//             const textCount = get_question_count(subject, levelValue, "", "Questions");
//             const audioCount = get_question_count(subject, levelValue, "", "Audios");
//             const fillupCount = get_question_count(subject, levelValue, "", "Fillups");
//             li.innerHTML += `<pre class="mb-0">${levelValue}: Text ${textCount}, Audio ${audioCount},Fillup ${fillupCount}</pre>`;

//             for (const subLevel of sub_levels) {
//                 const subLevelValue = subLevel[0];
//                 const subTextCount = get_question_count(subject, levelValue, subLevelValue, "Questions");
//                 const subAudioCount = get_question_count(subject, levelValue, subLevelValue, "Audios");
//                 const subFillupCount = get_question_count(subject, levelValue, subLevelValue, "Fillups");
//                 if (subTextCount > 0 || subAudioCount > 0 || subFillupCount > 0) {
//                     li.innerHTML += `<pre class="mb-0"> ${subLevelValue}: Text ${subTextCount}, Audio ${subAudioCount}, Fillup ${subFillupCount}</pre>`;
//                 }
//             }
//         }
//         listContainer.appendChild(li);
//     }
// }

function toggleInput(questionType) {
    const inputDiv = document.getElementById(`${questionType}_input`);
    const checkbox = document.getElementById(questionType);
    if (checkbox.checked) {
        inputDiv.style.display = "block";
    } else {
        inputDiv.style.display = "none";
        const inputField = document.querySelector(`#${questionType}_input input`);
        if (inputField) inputField.value = "0";
    }
    renderSublevelDistribution();
    updateFlatCountsFromLevel();
}

function toggleSubLevel() {
    // Called on subject change from HTML.
    resetCountValues();
    renderSublevelDistribution({ resetValues: true });
    updateFlatCountsFromLevel();
}

function updateFlatCountsFromLevel() {
    if (hasSublevelsForSelection()) {
        return;
    }

    const subject = getSelectedSubjectLabel();
    const level = document.getElementById("level").value;

    Object.entries(questionTypeMeta).forEach(([checkboxKey, meta]) => {
        const checkbox = document.getElementById(checkboxKey);
        const input = document.getElementById(meta.countInput);
        if (!input) return;

        const available = get_question_count(subject, level, "", meta.totalKey);
        input.max = String(available);

        let current = parseInt(input.value || "0", 10);
        if (Number.isNaN(current) || current < 0) current = 0;

        // For flat subjects, selecting a type should directly pick from chosen level.
        // Pre-fill with available count if user has not entered a value yet.
        if (checkbox?.checked && current === 0 && available > 0) {
            input.value = String(available);
            current = available;
        }

        if (current > available) {
            input.value = String(available);
        }
    });
}

function getDistribution() {
    const raw = document.getElementById("sublevel_distribution_json").value || "{}";
    return JSON.parse(raw);
}

function validateSublevelType(subject, level, distribution, checkboxKey) {
    const meta = questionTypeMeta[checkboxKey];
    const data = distribution[meta.distKey] || {};
    const requested = Object.values(data).reduce((a, b) => a + parseInt(b || 0, 10), 0);
    if (requested <= 0) {
        alert(`Please enter sublevel-wise counts for ${meta.label}.`);
        return false;
    }
    for (const [sub, cnt] of Object.entries(data)) {
        const available = get_question_count(subject, level, sub, meta.totalKey);
        if (parseInt(cnt, 10) > available) {
            alert(`Only ${available} ${meta.label} are available for ${subject} - ${level} - ${sub}`);
            return false;
        }
    }
    return true;
}

function validateFlatType(subject, level, form, checkboxKey) {
    const meta = questionTypeMeta[checkboxKey];
    const requested = parseInt(form[meta.countInput]?.value || 0, 10);
    const available = get_question_count(subject, level, "", meta.totalKey);
    if (requested <= 0) {
        alert(`Please enter the number of ${meta.label}`);
        return false;
    }
    if (requested > available) {
        alert(`Only ${available} ${meta.label} are available for ${subject} - ${level}`);
        return false;
    }
    return true;
}

function validateForm(form, totalQuestions) {
    try {
        const level = form.level?.value || "";
        if (!level) {
            alert("Please select the Level ");
            return false;
        }

        const subjectId = form.subject?.value || "";
        if (!subjectId) {
            alert("Please select the Subject ");
            return false;
        }

        const checkedTypes = Object.keys(questionTypeMeta).filter((key) => form[key].checked);
        if (!checkedTypes.length) {
            alert("Please select the question type ");
            return false;
        }

        const subject = getSelectedSubjectLabel();
        if (hasSublevelsForSelection()) {
            const distribution = getDistribution();
            for (const typeKey of checkedTypes) {
                if (!validateSublevelType(subject, level, distribution, typeKey)) return false;
            }
            return true;
        }

        for (const typeKey of checkedTypes) {
            if (!validateFlatType(subject, level, form, typeKey)) return false;
        }
        return true;
    } catch (error) {
        console.error("Validation crashed:", error);
        alert("Something went wrong. Please check the console.");
        return false;
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // buildQuestionCountsList();
    renderSublevelDistribution({ resetValues: true });
    updateFlatCountsFromLevel();
    document.getElementById("level").addEventListener("change", () => {
        renderSublevelDistribution({ resetValues: true });
        updateFlatCountsFromLevel();
    });
});
