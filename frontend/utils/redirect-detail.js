export const redirectDetail = (url, id) => {
  if (url) {
    let newUrl = url
    if (id) {
      newUrl += '?id=' + id
    }
    const newWindow = window.open(newUrl, '_blank');
    if (newWindow) {
      newWindow.focus();
    }
  }
}