const reviews = [
  {
    name: "1xBet",
    rating: "⭐️⭐️⭐️⭐️",
    text: "Wide range of markets, fast payouts, and a generous welcome bonus.",
    logo: "1xbet.jpg",
    link: "https://your-affiliate-link.com/1xbet"
  },
  {
    name: "Sportaza",
    rating: "⭐️⭐️⭐️⭐️",
    text: "Modern bookmaker with esports, live betting and frequent promotions.",
    logo: "sportaza.jpg",
    link: "https://your-affiliate-link.com/sportaza"
  },
  {
    name: "20Bet",
    rating: "⭐️⭐️⭐️⭐️",
    text: "User-friendly bookmaker with good odds and fast withdrawals.",
    logo: "20bet.jpg",
    link: "https://your-affiliate-link.com/20bet"
  },
  {
    name: "5Gringos",
    rating: "⭐️⭐️⭐️⭐️",
    text: "Fun themed bookmaker with competitive bonuses and sportsbook variety.",
    logo: "5gringos.jpg",
    link: "https://your-affiliate-link.com/5gringos"
  }
];

const container = document.getElementById("reviews-container");

reviews.forEach(r => {
  container.innerHTML += `
    <div class="review">
      <img src="${r.logo}" alt="${r.name} logo" style="max-width:200px; margin-bottom:10px;">
      <h3>${r.name} ${r.rating}</h3>
      <p>${r.text}</p>
      <a href="${r.link}" target="_blank" class="btn">Visit ${r.name}</a>
    </div>
  `;
});