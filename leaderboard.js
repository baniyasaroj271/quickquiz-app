const filter = document.querySelector('#quiz-filter');
const loading = document.querySelector('#leaderboard-loading');
const empty = document.querySelector('#leaderboard-empty');
const tableWrap = document.querySelector('#leaderboard-table-wrap');
const body = document.querySelector('#leaderboard-body');
const currentRank = document.querySelector('#current-rank');

function formatDuration(seconds) {
	const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
	const remaining = (seconds % 60).toString().padStart(2, '0');
	return `${minutes}:${remaining}`;
}

async function loadLeaderboard() {
	loading.hidden = false;
	empty.hidden = true;
	tableWrap.hidden = true;
	try {
		const response = await fetch(`/api/leaderboard?quiz=${encodeURIComponent(filter.value)}`);
		if (!response.ok) throw new Error('Could not load leaderboard.');
		const data = await response.json();
		loading.hidden = true;
		if (data.current_rank) {
			currentRank.textContent = `${data.current_username}, your current rank is #${data.current_rank}.`;
			currentRank.hidden = false;
		} else {
			currentRank.hidden = true;
		}
		if (!data.entries.length) {
			empty.hidden = false;
			return;
		}
		body.innerHTML = '';
		data.entries.forEach((entry) => {
			const row = document.createElement('tr');
			row.innerHTML = `<td><span class="rank-number">${entry.rank}</span></td><td class="leaderboard-name"></td><td>${entry.score}</td><td>${entry.percentage}%</td><td>${formatDuration(entry.completion_seconds)}</td>`;
			row.querySelector('.leaderboard-name').textContent = entry.username;
			if (entry.username === data.current_username) row.classList.add('current-user');
			if (entry.rank <= 3) row.classList.add(`top-rank-${entry.rank}`);
			body.appendChild(row);
		});
		tableWrap.hidden = false;
	} catch (error) {
		loading.textContent = error.message;
	}
}

filter.addEventListener('change', loadLeaderboard);
loadLeaderboard();