document.addEventListener("DOMContentLoaded", function () {
    const filter = document.getElementById("levelFilter");
    const subjectFilter = document.getElementById("subjectFilter");
    const contentBlocks = document.querySelectorAll(".content-block");

    function applyLevelFilter() {
        const selectedLevel = filter.value;
        const selectedSubject = subjectFilter.value;
        const noQuestionsMessage = document.getElementById("noQuestionsMessage");
        let totalVisibleCount = 0;

        contentBlocks.forEach((block) => {
            const items = block.querySelectorAll("li[data-level]");
            let visibleCount = 0;

            items.forEach((item) => {
                const levelMatch = !selectedLevel || item.dataset.level === selectedLevel;
                const subjectMatch = !selectedSubject || item.dataset.subject === selectedSubject;
                const match = levelMatch && subjectMatch;
                item.style.display = match ? "" : "none";
                if (match) visibleCount += 1;
            });

            block.style.display = visibleCount ? "" : "none";
            totalVisibleCount += visibleCount;
        });

        noQuestionsMessage.style.display = totalVisibleCount ? "none" : "block";
    }

    filter.addEventListener("change", applyLevelFilter);
    subjectFilter.addEventListener("change", applyLevelFilter);
});