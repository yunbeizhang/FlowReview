'use strict';

const dialog = document.getElementById('figure-dialog');
const dialogImage = document.getElementById('dialog-image');
document.querySelectorAll('[data-figure]').forEach(button => {
  button.addEventListener('click', () => {
    const source = button.querySelector('img');
    dialogImage.src = button.dataset.figure;
    dialogImage.alt = source.alt;
    dialogImage.style.width = source.naturalWidth < 1300 ? `${Math.min(source.naturalWidth, 900)}px` : '100%';
    document.getElementById('figure-dialog-title').textContent = button.dataset.figureTitle;
    dialog.showModal();
    const wrap = dialog.querySelector('.dialog-image-wrap');
    wrap.scrollTop = 0;
    wrap.scrollLeft = 0;
  });
});
dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});

let copyTimer;
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    clearTimeout(copyTimer);
    const target = document.getElementById(button.dataset.copy);
    const status = document.getElementById('copy-status');
    try {
      await navigator.clipboard.writeText(target.textContent);
      button.textContent = 'Copied';
      status.textContent = 'Content copied to clipboard.';
    } catch {
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = 'Selected';
      status.textContent = 'Content selected. Use your keyboard to copy.';
    }
    copyTimer = setTimeout(() => { button.textContent = 'Copy'; status.textContent = ''; }, 2200);
  });
});
