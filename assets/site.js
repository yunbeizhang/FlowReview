'use strict';

const heroButtons = document.querySelectorAll('[data-hero-policy]');
heroButtons.forEach(button => {
  button.addEventListener('click', () => {
    const allowed = button.dataset.heroPolicy === 'allow';
    heroButtons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    const outcome = document.getElementById('hero-outcome');
    outcome.className = `hero-outcome ${allowed ? 'is-allowed' : 'is-denied'}`;
    outcome.querySelector('.status-symbol').textContent = allowed ? '✓' : '×';
    outcome.querySelector('strong').textContent = allowed ? 'Execute the required action' : 'Block the action';
  });
});

const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
function selectTab(tab) {
  tabs.forEach(item => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
  });
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    selectTab(tabs[next]);
    tabs[next].focus();
  });
});

function updateComposition() {
  const global = document.querySelector('input[name="reader"]:checked').value === 'global';
  const allowed = document.querySelector('input[name="case-policy"]:checked').value === 'allow';
  const outcome = document.getElementById('composition-outcome');
  const unsafe = !allowed && !global;
  outcome.className = `case-outcome ${unsafe ? 'is-unsafe' : 'is-correct'}`;
  outcome.querySelector('.outcome-symbol').textContent = unsafe ? '×' : '✓';
  outcome.querySelector('strong').textContent = allowed ? 'Authorized use completed' : global ? 'Denied action blocked' : 'Denied action committed';
  outcome.querySelector('p').textContent = allowed
    ? global ? 'The combined view identifies the governed object. The commit gate permits its authorized use.' : 'Individual-artifact review permits the action. Authorized supply succeeds in this case.'
    : global ? 'The combined view identifies the governed object. The commit gate enforces DENY.' : 'No individual artifact resolves the complete object. The composed credential is committed despite DENY.';
  outcome.querySelector('.outcome-metric').textContent = allowed ? 'A = 1' : global ? 'D = 0' : 'D = 1';
  document.getElementById('composition-pair').textContent = global
    ? 'C = 1 · denied use blocked and authorized use completed'
    : 'C = 0 · denied and authorized uses both committed';
}
document.querySelectorAll('input[name="reader"], input[name="case-policy"]').forEach(input => input.addEventListener('change', updateComposition));

function updatePermission() {
  const specialist = document.querySelector('input[name="selector"]:checked').value === 'specialist';
  const outcome = document.getElementById('permission-outcome');
  outcome.className = `case-outcome ${specialist ? 'is-correct' : 'is-unsafe'}`;
  outcome.querySelector('.outcome-symbol').textContent = specialist ? '✓' : '×';
  outcome.querySelector('strong').textContent = specialist ? 'Correctly bound action committed' : 'Required authorized action rejected';
  outcome.querySelector('p').textContent = specialist
    ? 'The specialist selects the unchanged candidate. The runtime verifies the object, operation, destination, principal, and policy version.'
    : 'The selected object reference contains an extra period. The runtime rejects the action because its binding does not match.';
}
document.querySelectorAll('input[name="selector"]').forEach(input => input.addEventListener('change', updatePermission));

const commands = {
  openai: 'export OPENAI_API_KEY="your-key"\nuv run flowreview run --suite assembly \\\n  --model gpt-4.1-mini --output runs/assembly',
  anthropic: 'export ANTHROPIC_API_KEY="your-key"\nuv run flowreview run --suite assembly \\\n  --provider anthropic --model claude-sonnet-4-5 \\\n  --output runs/claude',
  bedrock: 'uv sync --extra bedrock\nexport AWS_PROFILE="your-profile"\nuv run --extra bedrock flowreview run --suite assembly \\\n  --provider bedrock --model your-bedrock-model-id \\\n  --region us-east-1 --output runs/bedrock',
  local: 'export OPENAI_API_KEY="local"\nuv run flowreview run --suite assembly --model your-model \\\n  --base-url http://localhost:8000/v1 \\\n  --token-parameter max_tokens --output runs/local'
};
const provider = document.getElementById('provider');
function updateProvider() {
  document.querySelector('#run-code code').textContent = commands[provider.value];
}
provider.addEventListener('change', updateProvider);

const resetTimers = new WeakMap();
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const target = document.getElementById(button.dataset.copy);
    clearTimeout(resetTimers.get(button));
    const status = document.getElementById('copy-status');
    try {
      await navigator.clipboard.writeText(target.textContent);
      button.textContent = 'Copied';
      status.textContent = 'Commands copied to clipboard.';
    } catch {
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = 'Selected';
      status.textContent = 'Commands selected. Use your keyboard to copy.';
    }
    resetTimers.set(button, setTimeout(() => { button.textContent = 'Copy'; status.textContent = ''; }, 2200));
  });
});

const dialog = document.getElementById('figure-dialog');
const dialogImage = document.getElementById('dialog-image');
document.querySelectorAll('[data-figure]').forEach(button => {
  button.addEventListener('click', () => {
    dialogImage.src = button.dataset.figure;
    dialogImage.alt = button.querySelector('img').alt;
    document.getElementById('figure-dialog-title').textContent = button.dataset.figureTitle;
    dialog.showModal();
    const imageWrap = dialog.querySelector('.dialog-image-wrap');
    imageWrap.scrollTop = 0;
    imageWrap.scrollLeft = 0;
  });
});
dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});

const progress = document.querySelector('.reading-progress');
let scrollPending = false;
function updateProgress() {
  const total = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.transform = `scaleX(${total > 0 ? Math.min(1, Math.max(0, window.scrollY / total)) : 0})`;
  scrollPending = false;
}
function requestProgress() {
  if (scrollPending) return;
  scrollPending = true;
  requestAnimationFrame(updateProgress);
}
window.addEventListener('scroll', requestProgress, { passive: true });
window.addEventListener('resize', requestProgress);
window.addEventListener('load', requestProgress);
updateComposition();
updatePermission();
updateProvider();
updateProgress();
