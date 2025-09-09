const analyses = [
  {
    home: "Croatia",
    away: "Faroe Islands",
    date: "2025-09-10",
    competition: "UEFA Qualifiers",
    stadium: "Zagreb Stadium",
    analysis: "Croatia remain strong favorites despite missing a few regular starters. Their squad depth and attacking quality should be enough to dominate the Faroe Islands, who struggle defensively.",
    formHome: ["W","W","L","D","W"],
    formAway: ["L","L","D","L","W"],
    winRateHome: 70,
    winRateAway: 20,
    goalsScoredHome: 9,
    goalsConcededHome: 4,
    goalsScoredAway: 3,
    goalsConcededAway: 11,
    tip: "Croatia -1.5 Handicap",
    odds: 1.75,
    link: "https://your-affiliate-link.com/croatia"
  }
];

const container = document.getElementById("analyses-container");

analyses.forEach((m, i) => {
  container.innerHTML += `
    <div class="analysis">
      <h3>${m.home} vs ${m.away}</h3>
      <p><b>Date:</b> ${m.date} | <b>Competition:</b> ${m.competition}</p>
      <p>${m.analysis}</p>
      <div class="bet-box">
        💡 Tip: ${m.tip} @ ${m.odds}
        <br>
        <a href="${m.link}" target="_blank" class="btn">Bet now with 100% Bonus</a>
      </div>
    </div>
  `;
});