async function naloziAnalize(containerId) {
    const response = await fetch('data.json');
    const data = await response.json();
    const container = document.getElementById(containerId);

    data.analize.forEach((a, index) => {
        const predlogStave = (a.formaDomaci > a.formaGostje) ? "1" : (a.formaGostje > a.formaDomaci ? "2" : "X");
        const povprecje = (arr) => (arr.reduce((x,y)=>x+y,0)/arr.length).toFixed(1);

        const article = document.createElement('article');
        article.innerHTML = `
            <h2>${a.sport}: ${a.tekma}</h2>
            <p><strong>Verjetnost domačega:</strong> ${(a.formaDomaci*100).toFixed(0)}%</p>
            <p><strong>Verjetnost gostujočega:</strong> ${(a.formaGostje*100).toFixed(0)}%</p>
            <p><strong>Povprečni rezultat zadnjih 5 tekem:</strong> ${povprecje(a.rezultati)}</p>
            <p><strong>Predlog stave:</strong> ${predlogStave}</p>
            <canvas id="chart-${index}" width="300" height="150"></canvas>
            <canvas id="trend-${index}" width="300" height="150"></canvas>
            <p><a href="${a.affiliate}" target="_blank" class="btn">Registriraj se in prejmi bonus</a></p>
        `;
        container.appendChild(article);

        // Graf verjetnosti zmage
        const ctx = document.getElementById(`chart-${index}`).getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Domači','Gostje'],
                datasets: [{ label:'Verjetnost zmage (%)', data:[a.formaDomaci*100, a.formaGostje*100], backgroundColor:['#ff9900','#0099ff'] }]
            },
            options: { scales:{y:{beginAtZero:true, max:100}} }
        });

        // Graf trendov zadnjih 5 tekem
        const ctx2 = document.getElementById(`trend-${index}`).getContext('2d');
        new Chart(ctx2, {
            type: 'line',
            data: {
                labels:['Tekma1','Tekma2','Tekma3','Tekma4','Tekma5'],
                datasets:[{label:'Rezultat / točke', data:a.rezultati, borderColor:'#00cc66', fill:false, tension:0.2}]
            },
            options:{scales:{y:{beginAtZero:true}}}
        });
    });
}

if(document.getElementById('analize-container')){ naloziAnalize('analize-container'); }