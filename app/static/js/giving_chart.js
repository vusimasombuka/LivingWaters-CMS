document.addEventListener("DOMContentLoaded", function () {
    const dataEl = document.getElementById("giving-data");
    if (!dataEl) return;

    const months = JSON.parse(dataEl.dataset.months);
    const totals = JSON.parse(dataEl.dataset.totals);

    const canvas = document.getElementById("givingChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    new Chart(ctx, {
        type: "bar",
        data: {
            labels: months,
            datasets: [{
                label: "Monthly Giving (R)",
                data: totals,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
});