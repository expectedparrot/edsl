document.addEventListener('DOMContentLoaded', function() {
    const collapsibleSections = document.querySelectorAll('.exception-detail, .raw-model-response');

    collapsibleSections.forEach(section => {
        const header = section.querySelector('.exception-header, .response-header');
        const content = section.querySelector('.exception-content, .response-content');
        const toggleBtn = section.querySelector('.toggle-btn');

        header.addEventListener('click', function() {
            content.classList.toggle('show');
            toggleBtn.classList.toggle('rotated');
        });
    });

});

function copyCode() {
    const textarea = document.getElementById('codeToCopy');
    textarea.select();
    textarea.setSelectionRange(0, 99999); // For mobile devices
    document.execCommand("copy");

    // Optionally, you can display an alert or change the button text to indicate success
    alert("Code copied to clipboard!");
}
