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