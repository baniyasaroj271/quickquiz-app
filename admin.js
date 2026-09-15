document.querySelectorAll('[data-delete-form]').forEach((form) => {
	form.addEventListener('submit', (event) => {
		if (!window.confirm('Delete this question? This action cannot be undone.')) {
			event.preventDefault();
		}
	});
});