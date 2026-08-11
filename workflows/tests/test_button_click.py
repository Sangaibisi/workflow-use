"""Live-browser integration test for button-click text filtering.

Launches a real browser against a demo form site - skipped by default;
run with RUN_BROWSER_TESTS=1 to include it.
"""

import asyncio
import logging
import os

import pytest
from browser_use import Browser

from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

pytestmark = pytest.mark.skipif(
	not os.environ.get('RUN_BROWSER_TESTS'),
	reason='Live-browser integration test; set RUN_BROWSER_TESTS=1 to run',
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _fill_by_selector(executor: SemanticWorkflowExecutor, selector: str, value: str) -> None:
	"""Page.fill doesn't exist on the CDP surface; fill the first matching Element."""
	elements = await executor._get_elements_by_selector(selector)
	assert elements, f'No element for {selector}'
	await elements[0].fill(value)


async def test_button_click():
	browser = Browser()
	await browser.start()
	executor = SemanticWorkflowExecutor(browser)

	try:
		# Navigate to the form page
		page = await browser.get_current_page()
		await page.goto('https://v0-complex-form-example.vercel.app/')
		await asyncio.sleep(2)

		# Click "Start Application" button
		logger.info("===Testing 'Start Application' button click===")
		success1 = await executor._click_element_intelligently('button', 'Start Application')
		logger.info(f'Start Application click: {"SUCCESS" if success1 else "FAILED"}')

		await asyncio.sleep(3)

		# Fill some form fields quickly (CDP has no page.fill/page.check)
		await _fill_by_selector(executor, '#firstName', 'Test')
		await _fill_by_selector(executor, '#lastName', 'User')
		await _fill_by_selector(executor, '#socialSecurityLast4', '1234')
		await executor._set_checked_by_selector('#male')
		await executor._set_checked_by_selector('#single')
		await asyncio.sleep(1)

		# Get all buttons before clicking
		all_buttons = await executor._get_elements_by_selector('button')
		logger.info(f'Total buttons on page: {len(all_buttons)}')

		# Click "Next: Contact Information" button
		logger.info("===Testing 'Next: Contact Information' button click===")
		success2 = await executor._click_element_intelligently('button', 'Next: Contact Information')
		logger.info(f'Next button click: {"SUCCESS" if success2 else "FAILED"}')

		await asyncio.sleep(2)

		# Check final URL
		final_url = page.url
		logger.info(f'Final URL: {final_url}')
		if '/contact-info' in final_url:
			logger.info('✅ SUCCESS: Navigated to contact info page!')
		else:
			logger.error('❌ FAILED: Still on personal info page')

	finally:
		await browser.close()


if __name__ == '__main__':
	asyncio.run(test_button_click())
