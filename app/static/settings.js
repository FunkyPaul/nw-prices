(() => {
  const boxes = [...document.querySelectorAll('#setCols input[data-col]')];
  if (!boxes.length) return;
  const hidden = new Set(hiddenCols());
  for (const b of boxes) b.checked = !hidden.has(b.dataset.col);

  function save() {
    const list = boxes.filter(b => !b.checked).map(b => b.dataset.col);
    toast(saveHiddenCols(list) ? t('set.saved') : t('set.save_failed'));
  }
  for (const b of boxes) b.addEventListener('change', save);
  document.getElementById('setAll').addEventListener('click', () => {
    for (const b of boxes) b.checked = true;
    save();
  });
})();
