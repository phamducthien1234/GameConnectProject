document.querySelectorAll(".group-choice").forEach(function (select) {
    select.addEventListener("change", function () {
        const form = select.closest("form");
        const fields = form.querySelector(".new-group-fields");
        const input = fields.querySelector("input");

        if (select.value === "new") {
            fields.classList.remove("d-none");
            input.required = true;
        } else {
            fields.classList.add("d-none");
            input.required = false;
            input.value = "";
        }
    });
});