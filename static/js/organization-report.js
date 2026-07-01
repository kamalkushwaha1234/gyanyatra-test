let allReportRows = (window.default_rows_json) || (document.getElementById('default_rows_json')?.value) || null;
    let defaultReportRows = [...allReportRows];

function getSelectedFilters() {
    const startDate = document.getElementById("start-date-filter").value;
    const endDate = document.getElementById("end-date-filter").value;
    const organizationId = document.getElementById("organization-filter").value;
    const assessmentId = document.getElementById("assessment-filter").value;
    return { startDate, endDate, organizationId, assessmentId };
}

function validateDateRange() {
    const tableBody = document.getElementById("report-table-body");
    const alertBox = document.getElementById("report-alert");
    const { startDate, endDate } = getSelectedFilters();
    const today = new Date();

    if ((startDate && new Date(startDate) > today) || (endDate && new Date(endDate) > today)) {
        tableBody.innerHTML = "";
        alertBox.className = "alert alert-danger my-2 mx-4";
        alertBox.innerHTML = "<p>Future dates are not allowed. Please select a valid date range.</p>";
        return false;
    }

    if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
        tableBody.innerHTML = "";
        alertBox.className = "alert alert-danger my-2 mx-4";
        alertBox.innerHTML = "<p>Start Date cannot be greater than End Date.</p>";
        return false;
    }
    return true;
}

function applyFilters() {
    const tableBody = document.getElementById("report-table-body");
    const alertBox = document.getElementById("report-alert");
    const { startDate, endDate, organizationId, assessmentId } = getSelectedFilters();
    if (!validateDateRange()) return [];

    const filteredRows = allReportRows.filter((row) => {
        const rowDate = new Date(row.month_date);
        const startMatch = !startDate || rowDate >= new Date(startDate);
        const endMatch = !endDate || rowDate <= new Date(endDate);
        const organizationMatch = !organizationId || String(row.organization_id) === String(organizationId);
        const assessmentMatch = !assessmentId || String(row.assessment_id) === String(assessmentId);
        return startMatch && endMatch && organizationMatch && assessmentMatch;
    });

    tableBody.innerHTML = "";
    alertBox.className = "";
    alertBox.innerHTML = "";

    if (!filteredRows.length) {
        alertBox.className = "alert alert-warning my-2 mx-4";
        alertBox.innerHTML = "<p>No data found.</p>";
        return filteredRows;
    }

    const total = filteredRows.reduce((sum, row) => sum + (row.assessments || 0), 0);
    const totalRow = document.createElement("tr");
    totalRow.className = "fw-bold";
    totalRow.style.backgroundColor = "#00A79D";
    totalRow.style.color = "#ffffff";
    totalRow.innerHTML = `
        <td colspan="5">Total Assessment Result Count</td>
        <td>${total}</td>
    `;
    tableBody.appendChild(totalRow);

    filteredRows.forEach((row, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${row.year}</td>
            <td>${row.month}</td>
            <td>${row.organization_name || "-"}</td>
            <td>${row.assessment_name || "-"}</td>
            <td>${row.assessments}</td>
        `;
        tableBody.appendChild(tr);
    });

    return filteredRows;
}

function renderRows(rows) {
    const tableBody = document.getElementById("report-table-body");
    const alertBox = document.getElementById("report-alert");

    tableBody.innerHTML = "";
    alertBox.className = "";
    alertBox.innerHTML = "";

    if (!rows.length) {
        alertBox.className = "alert alert-warning my-2 mx-4";
        alertBox.innerHTML = "<p>No data found.</p>";
        return;
    }

    const total = rows.reduce((sum, row) => sum + (row.assessments || 0), 0);
    const totalRow = document.createElement("tr");
    totalRow.className = "fw-bold";
    totalRow.style.backgroundColor = "#00A79D";
    totalRow.style.color = "#ffffff";
    totalRow.innerHTML = `
        <td colspan="5">Total Assessment Result Count</td>
        <td>${total}</td>
    `;
    tableBody.appendChild(totalRow);

    rows.forEach((row, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${row.year}</td>
            <td>${row.month}</td>
            <td>${row.organization_name || "-"}</td>
            <td>${row.assessment_name || "-"}</td>
            <td>${row.assessments}</td>
        `;
        tableBody.appendChild(tr);
    });
}

function downloadFilteredReport() {
    const filteredRows = applyFilters();
    if (!filteredRows.length) return;

    const headers = ["S.No", "Year", "Month", "Organization", "Assessment Name", "Assessment"];
    const csvRows = [headers.join(",")];

    const total = filteredRows.reduce((sum, row) => sum + (row.assessments || 0), 0);
    csvRows.push(`"Total Assessment Result Count","","","","",${total}`);

    filteredRows.forEach((row, index) => {
        const values = [
            index + 1,
            row.year,
            row.month,
            `"${String(row.organization_name || "-").replace(/"/g, '""')}"`,
            `"${String(row.assessment_name || "-").replace(/"/g, '""')}"`,
            row.assessments,
        ];
        csvRows.push(values.join(","));
    });

    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const now = new Date();
    const timestamp = now.toISOString().slice(0, 19).replace(/[:T]/g, "-");
    link.href = url;
    link.download = `organization-report-${timestamp}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function fetchOrganizationReport() {
    const { startDate, endDate, organizationId, assessmentId } = getSelectedFilters();
    if (!validateDateRange()) return;

    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (organizationId) params.append("organization_id", organizationId);
    if (assessmentId) params.append("assessment_id", assessmentId);

    fetch(`/api/organization-report/?${params.toString()}`)
        .then((response) => response.json())
        .then((data) => {
            allReportRows = data.results || [];
            renderRows(allReportRows);
        })
        .catch(() => {
            const alertBox = document.getElementById("report-alert");
            alertBox.className = "alert alert-danger my-2 mx-4";
            alertBox.innerHTML = "<p>Error loading report data.</p>";
        });
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("apply-filter").addEventListener("click", fetchOrganizationReport);
    document.getElementById("reset-filter").addEventListener("click", function () {
        document.getElementById("start-date-filter").value = "{{ default_start_date }}";
        document.getElementById("end-date-filter").value = "{{ default_end_date }}";
        document.getElementById("organization-filter").value = "";
        document.getElementById("assessment-filter").value = "";
        allReportRows = [...defaultReportRows];
        renderRows(allReportRows);
    });
    document.getElementById("download-report").addEventListener("click", downloadFilteredReport);

    renderRows(defaultReportRows);
});