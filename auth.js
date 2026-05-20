const supabaseClient = window.supabase.createClient(
  'https://lsnycmyxzjiuhqjrfbmm.supabase.co',
  'sb_publishable_OBi3M5SABG9RXhGkGgmQgg_dpx_fjxm'
);

function getRedirectUrl() {
  const path = window.location.pathname || '/prognoze.html';
  if (path.includes('premium.html')) return 'https://magicbetting.netlify.app/premium.html';
  return 'https://magicbetting.netlify.app/prognoze.html';
}

async function signIn(email) {
  const { error } = await supabaseClient.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: getRedirectUrl()
    }
  });

  if (error) {
    alert(error.message);
    return;
  }

  alert('Provjeri email za login link.');
}

async function getCurrentUser() {
  const {
    data: { user }
  } = await supabaseClient.auth.getUser();

  return user;
}

async function getUserProfile() {
  const user = await getCurrentUser();
  if (!user) return { user: null, profile: null, error: null };

  const { data, error } = await supabaseClient
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();

  return { user, profile: data || null, error };
}

async function userHasAccess() {
  const { profile } = await getUserProfile();
  if (!profile) return false;

  const now = new Date();
  const trialEnd = new Date(profile.trial_ends_at);

  return profile.subscription_status === 'active' || now < trialEnd;
}

async function getAccessState() {
  const { user, profile } = await getUserProfile();

  if (!user) {
    return {
      status: 'guest',
      user: null,
      profile: null,
      hasAccess: false,
      label: 'Nisi prijavljen'
    };
  }

  if (!profile) {
    return {
      status: 'missing_profile',
      user,
      profile: null,
      hasAccess: false,
      label: 'Profil nije pronađen'
    };
  }

  const now = new Date();
  const trialEnd = new Date(profile.trial_ends_at);
  const trialActive = now < trialEnd;
  const paidActive = profile.subscription_status === 'active';

  if (paidActive) {
    return {
      status: 'premium',
      user,
      profile,
      hasAccess: true,
      label: 'AI77 Premium aktivan'
    };
  }

  if (trialActive) {
    const msLeft = trialEnd.getTime() - now.getTime();
    const hoursLeft = Math.max(0, Math.ceil(msLeft / 1000 / 60 / 60));
    const daysLeft = Math.floor(hoursLeft / 24);
    const restHours = hoursLeft % 24;

    return {
      status: 'trial',
      user,
      profile,
      hasAccess: true,
      label: `Trial aktivan još ${daysLeft}d ${restHours}h`
    };
  }

  return {
    status: 'expired',
    user,
    profile,
    hasAccess: false,
    label: 'Trial je istekao'
  };
}

async function startTrial() {
  const input = document.getElementById('trialEmail');
  const email = input ? input.value.trim() : '';

  if (!email) {
    alert('Unesi email');
    return;
  }

  await signIn(email);
}

async function signOutAI77() {
  await supabaseClient.auth.signOut();
  window.location.reload();
}

function renderGuestBox(root) {
  root.innerHTML = `
    <div class="premium-status-top">
      <span class="partner-badge">AI77 Premium</span>
      <span class="premium-price">3 dana besplatno</span>
    </div>
    <h2>Otključaj AI77 Premium</h2>
    <p>Dobij pristup svim AI pickovima 3 dana besplatno. Bez kartice.</p>
    <div class="trial-form">
      <input type="email" id="trialEmail" placeholder="Unesi email">
      <button class="btn primary" onclick="startTrial()">Pokreni 3 dana besplatno</button>
    </div>
    <p class="fineprint premium-note">Nakon triala možeš nastaviti kroz AI77 Premium pretplatu. Nema garantovanih rezultata.</p>
  `;
}

function renderActiveBox(root, state) {
  root.innerHTML = `
    <div class="premium-status-top">
      <span class="partner-badge success">Aktivno</span>
      <span class="premium-price">${state.status === 'premium' ? 'Premium član' : 'Free trial'}</span>
    </div>
    <h2>AI77 Premium je otključan ✅</h2>
    <p>${state.label}. Svi aktivni premium pickovi su dostupni na ovoj stranici.</p>
    <div class="inline-actions">
      <a class="btn primary" href="prognoze.html#aktivni">Pogledaj pickove</a>
      <button class="btn" type="button" onclick="signOutAI77()">Odjava</button>
    </div>
  `;
}

function renderExpiredBox(root) {
  root.innerHTML = `
    <div class="premium-status-top">
      <span class="partner-badge">Trial istekao</span>
      <span class="premium-price">99€/mj</span>
    </div>
    <h2>Nastavi AI77 Premium</h2>
    <p>Tvoj besplatni pristup je istekao. Nastavi s premium pristupom za sve AI77 pickove.</p>
    <div class="inline-actions">
      <a class="btn primary" href="premium.html#pricing">Nastavi Premium</a>
      <button class="btn" type="button" onclick="signOutAI77()">Odjava</button>
    </div>
  `;
}

async function renderPremiumAccessBoxes() {
  const boxes = document.querySelectorAll('[data-premium-access-box]');
  if (!boxes.length) return;

  const state = await getAccessState();

  boxes.forEach((root) => {
    if (state.status === 'trial' || state.status === 'premium') {
      renderActiveBox(root, state);
    } else if (state.status === 'expired') {
      renderExpiredBox(root);
    } else {
      renderGuestBox(root);
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  renderPremiumAccessBoxes();
});

window.startTrial = startTrial;
window.userHasAccess = userHasAccess;
window.getAccessState = getAccessState;
window.signOutAI77 = signOutAI77;
