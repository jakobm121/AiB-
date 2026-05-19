const supabaseClient = window.supabase.createClient(
  'https://lsnycmyxzjiuhqjrfbmm.supabase.co',
  'sb_publishable_OBi3M5SABG9RXhGkGgmQgg_dpx_fjxm'
);

async function signIn(email) {
  const { error } = await supabaseClient.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: 'https://magicbetting.netlify.app/prognoze.html'
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

async function userHasAccess() {
  const user = await getCurrentUser();
  if (!user) return false;

  const { data, error } = await supabaseClient
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();

  if (error || !data) return false;

  const now = new Date();
  const trialEnd = new Date(data.trial_ends_at);

  return data.subscription_status === 'active' || now < trialEnd;
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

window.startTrial = startTrial;
window.userHasAccess = userHasAccess;
