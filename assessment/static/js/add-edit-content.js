(() => {

    // Utility function to safely normalize cell values, treating null/undefined as empty strings.
    function normalizeCell(value) {
        if (value === null || value === undefined) return "";
        return String(value).trim();
    }
    
    // Triggers the hidden file input for importing questions.
    function triggerImportQuestions() {
        const input = document.getElementById("import-template-file");
        if (!input) return;
        input.value = "";
        input.click();
    }

    // Creates a temporary link to trigger the browser's download functionality for a given Blob and filename.
    function triggerBrowserDownload(blob, fileName) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    // Attempts to download the sample template from the server API and triggers a browser download. Logs errors if the API call fails.
    async function downloadSampleTemplate() {
        try {
            const response = await fetch("/api/import-questions/sample-template/", {
                method: "GET",
            });
            if (!response.ok) {
                throw new Error(`Sample template API failed with status ${response.status}`);
            }
            const blob = await response.blob();
            triggerBrowserDownload(blob, "questions_template.xlsx");
            return;
        } catch (err) {
            console.error("Sample template API error:", err);
        }
    }

    // Retrieves the CSRF token from the page's hidden input field, returning an empty string if not found.
    function getCsrfToken() {
        const tokenInput = document.querySelector("input[name='csrfmiddlewaretoken']");
        return tokenInput ? tokenInput.value : "";
    }

    // Converts a base64-encoded string into a Blob object with the specified MIME type.
    function b64ToBlob(base64, mimeType) {
        const binary = atob(base64);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
        return new Blob([bytes], { type: mimeType || "application/octet-stream" });
    }

    // If the API returns an error file in base64 format, this function converts it to a Blob and triggers a download for the user.
    function downloadImportErrorFileFromApi(errorFileBase64, fileName) {
        if (!errorFileBase64) return;
        const blob = b64ToBlob(
            errorFileBase64,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        );
        triggerBrowserDownload(blob, fileName || "questions_import_errors.xlsx");
    }

    // Applies the imported data from the API response to the form fields, including content, level, subject, sub-level, and questions. Alerts the user if no importable questions are found or if the form state is not initialized.
    function applyImportedData(payload) {
        const content = normalizeCell(payload.content);
        const level = normalizeCell(payload.level);
        const subject = normalizeCell(payload.subject);
        const subLevel = normalizeCell(payload.sub_level);

        if (window.quill) window.quill.root.innerHTML = content;
        const contentTextarea = document.getElementById("content");
        if (contentTextarea) contentTextarea.value = content;

        const levelSelect = document.getElementById("level");
        const subjectSelect = document.getElementById("subject");
        const sublevelSelect = document.getElementById("sub_level");
        if (levelSelect) levelSelect.value = level;
        if (subjectSelect) {
            subjectSelect.value = subject;
            subjectSelect.dispatchEvent(new Event("change"));
        }
        if (sublevelSelect) sublevelSelect.value = subLevel;

        const importedQuestions = Array.isArray(payload.questions) ? payload.questions : [];
        if (!importedQuestions.length) {
            alert("No importable question rows found.");
            return;
        }
        if (window.mixedContentState) window.mixedContentState.fields = importedQuestions;
        else alert("Question form state not initialized. Please refresh and try again.");
    }

    // Initializes the import handlers by attaching a change event listener to the file input. When a file is selected, it sends the file to the API for validation and processing, then applies the imported data to the form or shows error messages as needed.
    function initImportHandlers() {
        const importInput = document.getElementById("import-template-file");
        if (!importInput) return;
        importInput.addEventListener("change", async (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;
            try {
                const formData = new FormData();
                formData.append("template_file", file);

                const response = await fetch("/api/import-questions/", {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrfToken() },
                    body: formData,
                });
                const payload = await response.json();

                if (!response.ok || !payload.success) {
                    const errors = Array.isArray(payload.errors) ? payload.errors : [];
                    const errorText = errors.length ? errors.join("\n- ") : (payload.message || "Import validation failed.");
                    alert(`Import validation failed:\n- ${errorText}`);
                    downloadImportErrorFileFromApi(payload.error_file_base64, payload.error_file_name);
                    return;
                }

                applyImportedData(payload);
                alert(payload.message || "Questions imported to form successfully.");
            } catch (err) {
                console.error("Import request error:", err);
                alert("Unable to process import file. Please try again.");
            }
        });
    }

    // Initializes the rich text editor (Quill) on the content textarea, setting up a toolbar with various formatting options. If the editor element is not found, it simply returns without initializing.
    function initEditor() {
        const editor = document.getElementById("contentEditor");
        if (!editor) return;
        const toolbarOptions = [
            ["bold", "italic", "underline", "strike"],
            ["blockquote", "code-block"],
            [{ header: 1 }, { header: 2 }],
            [{ list: "ordered" }, { list: "bullet" }],
            [{ script: "sub" }, { script: "super" }],
            [{ indent: "-1" }, { indent: "+1" }],
            [{ direction: "rtl" }],
            [{ size: ["small", false, "large", "huge"] }],
            [{ header: [1, 2, 3, 4, 5, 6, false] }],
            [{ color: [] }, { background: [] }],
            [{ font: [] }],
            [{ align: [] }],
            ["clean"],
        ];
        window.quill = new Quill("#contentEditor", {
            modules: { toolbar: toolbarOptions },
            theme: "snow",
        });
    }

    // Initializes protection for fill-in-the-blank questions by preventing modifications to the blank areas. It listens for keydown, paste, and drop events on textareas with the class "fillup-textarea" and checks if the selection overlaps with the blank placeholder. If it does, it prevents the action and alerts the user.
    function initFillupProtection() {
        const blankStr = "_____";
        const blankLength = blankStr.length;

        function isSelectionOverlappingBlank(value, start, end) {
            const regex = new RegExp(blankStr, "g");
            let match;
            while ((match = regex.exec(value)) !== null) {
                const blankStart = match.index;
                const blankEnd = blankStart + blankLength;
                const isInsideBlank = start >= blankStart && start <= blankEnd;
                if (isInsideBlank) return true;
                const overlaps = !(end <= blankStart || start >= blankEnd);
                if (overlaps) return true;
            }
            return false;
        }

        document.body.addEventListener("keydown", (e) => {
            if (!(e.target && e.target.classList.contains("fillup-textarea"))) return;
            const textarea = e.target;
            if (isSelectionOverlappingBlank(textarea.value, textarea.selectionStart, textarea.selectionEnd)) {
                if (e.key.length === 1 || e.key === "Backspace" || e.key === "Delete") {
                    e.preventDefault();
                    alert("You cannot modify the blank. Please type your answer beside it.");
                }
            }
        });

        document.body.addEventListener("paste", (e) => {
            const textarea = e.target;
            if (!(textarea && textarea.classList.contains("fillup-textarea"))) return;
            if (isSelectionOverlappingBlank(textarea.value, textarea.selectionStart, textarea.selectionEnd)) {
                e.preventDefault();
                alert("You cannot paste into a blank.");
            }
        });

        document.body.addEventListener("drop", (e) => {
            const textarea = e.target;
            if (!(textarea && textarea.classList.contains("fillup-textarea"))) return;
            if (isSelectionOverlappingBlank(textarea.value, textarea.selectionStart, textarea.selectionStart)) {
                e.preventDefault();
                alert("You cannot drop text into a blank.");
            }
        });
    }

    // Validates the form before submission, ensuring that the content field is not empty, all questions are filled, audio questions have files and answers, and the level is selected. If any validation fails, it alerts the user and prevents form submission. If all validations pass, it submits the form.
    function submitForm(form, e) {
        e.preventDefault();
        document.getElementById("content").value = (window.quill ? window.quill.root.innerHTML : "");

        const questions = document.querySelectorAll("textarea[id^='question']");
        const audioInputs = document.querySelectorAll("input[type='file'][id^='audio-question']");
        const audioPlayers = document.querySelectorAll("audio[id^='track']");
        const audioAnswers = document.querySelectorAll("textarea[id^='audio-answer']");
        const levelSelection = document.querySelector("#level");
        const fillup = document.querySelectorAll("textarea[id^='fillup']");
        const blank1 = document.querySelectorAll("input[id='blank1']");
        const blank2 = document.querySelectorAll("input[id='blank2']");
        const blank3 = document.querySelectorAll("input[id='blank3']");
        const blank4 = document.querySelectorAll("input[id='blank4']");
        const blank5 = document.querySelectorAll("input[id='blank5']");
        const blank6 = document.querySelectorAll("input[id='blank6']");
        const blank7 = document.querySelectorAll("input[id='blank7']");
        const blank8 = document.querySelectorAll("input[id='blank8']");
        const blank9 = document.querySelectorAll("input[id='blank9']");
        const blank10 = document.querySelectorAll("input[id='blank10']");

        const content = document.querySelector("#content");
        const contentValue = content.value.trim();
        if (contentValue.replace(/<[^>]*>/g, "") === "") {
            alert("Please fill the content field.");
            return;
        }

        for (let i = 0; i < questions.length; i++) {
            if (!questions[i].value.trim()) {
                const indexVal = questions[i].closest("[data-index]").dataset.index;
                alert(indexVal ? `Please fill the question ${indexVal}` : "Please fill the all question");
                return;
            }
        }

        for (let i = 0; i < fillup.length; i++) {
            if (!fillup[i].value.trim()) {
                const indexVal = fillup[i].closest("[data-index]").dataset.index;
                alert(indexVal ? `Please fill the question ${indexVal}` : "Please fill the all question");
                return;
            }
            const str = fillup[i].value.trim();
            const matches = str.match(/_{2,}/g);
            const count = matches ? matches.length : 0;
            if (count === 0) {
                const indexVal = fillup[i].closest("[data-index]").dataset.index;
                alert(indexVal ? `You have to add minimum one blank in Question ${indexVal}` : "You have to add minimum one blank in Question");
                return;
            }
            const blanks = [
                blank1[i]?.value.trim() || "",
                blank2[i]?.value.trim() || "",
                blank3[i]?.value.trim() || "",
                blank4[i]?.value.trim() || "",
                blank5[i]?.value.trim() || "",
                blank6[i]?.value.trim() || "",
                blank7[i]?.value.trim() || "",
                blank8[i]?.value.trim() || "",
                blank9[i]?.value.trim() || "",
                blank10[i]?.value.trim() || "",
            ];
            for (let k = 0; k < count; k++) {
                if (!blanks[k]) {
                    const indexVal = fillup[i].closest("[data-index]").dataset.index;
                    alert(indexVal ? `Please Fill the blank ${k + 1} of Question ${indexVal}` : `Please Fill the blank ${k + 1} of Question`);
                    return;
                }
            }
        }

        const questionBlocks = document.querySelectorAll(".question-block[data-index]");
        for (const q of questionBlocks) {
            const indexVal = q.dataset.index;
            const usedOptions = [...q.querySelectorAll("input[id^='option']")].filter((el) => el.offsetParent !== null);
            for (let i = 0; i < usedOptions.length; i++) {
                if (usedOptions[i].value.trim() === "") {
                    alert(`Kindly provide at least two options for question ${indexVal}. If there are more options, please fill them; otherwise, please remove them.`);
                    usedOptions[i].focus();
                    return;
                }
            }
        }

        for (let i = 0; i < audioPlayers.length; i++) {
            const audioInput = audioInputs[i];
            const audioPlayer = audioPlayers[i];
            const hasUploadedFile = audioInput?.files?.length > 0;
            const hasExistingAudio = audioPlayer?.src && audioPlayer.src.trim() !== "";
            const audioIndex = audioInput.closest("[data-index]").dataset.index;

            if (!hasUploadedFile && !hasExistingAudio) {
                alert(audioIndex ? `Please provide the file for Audio question ${audioIndex}` : "Please provide the file for all Audio questions");
                return;
            }
            if (hasUploadedFile) {
                const audioFile = audioInput.files[0];
                const sizeInMB = (audioFile.size / (1024 * 1024)).toFixed(2);
                if (sizeInMB > 2) {
                    alert(audioIndex ? `The file size for Audio question ${audioIndex} exceeds the 2 MB limit.` : "The file size for one of the Audio questions exceeds the 2 MB limit.");
                    return;
                }
                const allowedTypes = ["audio/mpeg", "audio/wav", "audio/mp3", "audio/ogg"];
                if (!allowedTypes.includes(audioFile.type)) {
                    alert(`Invalid audio file type for question ${audioIndex || ""}. Allowed formats are MP3, WAV, OGG.`);
                    return;
                }
            }
            if (!audioAnswers[i].value.trim()) {
                alert(audioIndex ? `Please enter the answer for Audio question ${audioIndex}` : "Please enter the answer for all Audio questions");
                return;
            }
        }

        if (!levelSelection.value) {
            alert("Please Select the level ");
            return;
        }
        form.submit();
    }

    window.triggerImportQuestions = triggerImportQuestions;
    window.downloadSampleTemplate = downloadSampleTemplate;
    window.submitForm = submitForm;

    document.addEventListener("DOMContentLoaded", () => {
        initEditor();
        initImportHandlers();
        initFillupProtection();
    });
})();
