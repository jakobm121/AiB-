async function naloziStavnice(containerId) {
    const response = await fetch('stavnice.json');
    const data = await response.json();
    const container = document.getElementById(containerId);

    data.stavnice.forEach(stavnica => {
        const article = document.createElement('article');
        article.innerHTML = `
            <h2>${stavnica.ime}</h2>
            <img src="${stavnica.logo}" alt="${stavnica.ime}" style="width:150px;">
            <ul>
                <li><strong>Bonus za nove igralce:</strong> ${stavnica.bonus}</li>
                <li><strong>Kvote:</strong> ${stavnica.kvote}</li>
                <li><strong>Mobilna aplikacija:</strong> ${stavnica.aplikacija}</li>
                <li><strong>Varstvo in licenca:</strong> ${stavnica.varnost}</li>
                <li><strong>Metode plačila:</strong> ${stavnica.placila}</li>
                <li><strong>Posebne funkcije:</strong> ${stavnica.funkcije}</li>
            </ul>
            <a href="${stavnica.affiliate}" target="_blank" class="btn">Registriraj se in prejmi bonus</a>
        `;
        container.appendChild(article);
    });
}

// Za stavnice.html
if(document.getElementById('stavnice-container')){
    naloziStavnice('stavnice-container');
}