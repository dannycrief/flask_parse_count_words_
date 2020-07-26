document.querySelector('#receivedLink').addEventListener('#receivedLink', () => {
    const value = this.value;
    if (!value.startsWith("http") || !value.startsWith("https")) {
        this.value += 'http://'
    }
    console.log(this.value);
}, false);