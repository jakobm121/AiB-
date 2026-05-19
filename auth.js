const supabase = window.supabase.createClient(
  'https://lsnycmyxzjiuhqjrfbmm.supabase.co/rest/v1/',
  'sb_publishable_OBi3M5SABG9RXhGkGgmQgg_dpx_fjxm'
);

async function signIn(email) {
  const { error } = await supabase.auth.signInWithOtp({
    email
  });

  if (error) {
    alert(error.message);
    return;
  }

  alert('Check your email for login link.');
}

async function getCurrentUser() {
  const {
    data: { user }
  } = await supabase.auth.getUser();

  return user;
}

async function userHasAccess() {
  const user = await getCurrentUser();

  if (!user) return false;

  const { data } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();

  if (!data) return false;

  const now = new Date();
  const trialEnd = new Date(data.trial_ends_at);

  return (
    data.subscription_status === 'active' ||
    now < trialEnd
  );
}

async function startTrial() {
  const email =
    document.getElementById('trialEmail').value;

  if (!email) {
    alert('Enter email');
    return;
  }

  await signIn(email);
}
