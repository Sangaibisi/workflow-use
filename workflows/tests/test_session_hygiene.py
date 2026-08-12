"""Recording-session hygiene, found by a live end-to-end tour.

A recorder browser left over from a previous session kept recording and its
accumulated events were saved into a brand-new recording. Two of the three
defenses live here (the third - discarding foreign persisted state - is in
the extension service worker):

- the recording server drops workflow steps timestamped before the session
  started;
- variable names transliterate to ASCII instead of eating non-ASCII letters.

Run with: ``uv run pytest tests/test_session_hygiene.py``
"""

from workflow_use.recorder.service import RecordingService
from workflow_use.recorder.views import HttpWorkflowUpdateEvent
from workflow_use.workflow.variable_identifier import VariableIdentifier


def _update_event(step_timestamps):
	steps = [
		{'type': 'navigation', 'url': f'https://site.example/{i}', 'timestamp': ts} if ts is not None else {'type': 'navigation', 'url': f'https://site.example/{i}'}
		for i, ts in enumerate(step_timestamps)
	]
	return HttpWorkflowUpdateEvent(
		timestamp=max([t for t in step_timestamps if t is not None], default=0),
		payload={
			'name': 'wf',
			'description': 'd',
			'version': '1.0',
			'input_schema': [],
			'steps': steps,
		},
	)


class TestPreSessionStepFilter:
	def _service(self, session_started_ms):
		service = RecordingService.__new__(RecordingService)  # skip FastAPI setup
		service.session_started_ms = session_started_ms
		return service

	def test_steps_from_a_previous_session_are_dropped(self):
		service = self._service(session_started_ms=1_000_000)
		event = _update_event([100_000, 200_000, 1_000_500])  # two stale, one fresh
		filtered = service._drop_pre_session_steps(event)
		urls = [s.url for s in filtered.payload.steps]
		assert urls == ['https://site.example/2']

	def test_fresh_steps_are_untouched(self):
		service = self._service(session_started_ms=1_000_000)
		event = _update_event([1_000_100, 1_200_000])
		filtered = service._drop_pre_session_steps(event)
		assert len(filtered.payload.steps) == 2

	def test_small_clock_skew_is_tolerated(self):
		service = self._service(session_started_ms=1_000_000)
		event = _update_event([997_000])  # 3s before start, within the 5s margin
		filtered = service._drop_pre_session_steps(event)
		assert len(filtered.payload.steps) == 1

	def test_untimestamped_steps_are_kept(self):
		service = self._service(session_started_ms=1_000_000)
		event = _update_event([None, 100_000])
		filtered = service._drop_pre_session_steps(event)
		assert len(filtered.payload.steps) == 1
		assert filtered.payload.steps[0].url == 'https://site.example/0'

	def test_no_session_start_means_no_filtering(self):
		service = self._service(session_started_ms=0)
		event = _update_event([100])
		filtered = service._drop_pre_session_steps(event)
		assert len(filtered.payload.steps) == 1


class TestVariableNameTransliteration:
	def _name(self, raw):
		return VariableIdentifier()._normalize_variable_name(raw)

	def test_turkish_label(self):
		"""'ü' used to be eaten: 'vikipedi_zerinde_ara'."""
		assert self._name('Vikipedi üzerinde ara') == 'vikipedi_uzerinde_ara'

	def test_all_turkish_letters(self):
		assert self._name('çğıöşü İĞÜŞÖÇ') == 'cgiosu_igusoc'

	def test_other_latin_diacritics(self):
		assert self._name('Prénom émigré') == 'prenom_emigre'

	def test_ascii_untouched(self):
		assert self._name('First Name') == 'first_name'
