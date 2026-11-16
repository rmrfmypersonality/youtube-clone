<template>
  <RouterLink to="/" class="logo" aria-label="YouTube Clone: на главную">
    <svg width="28" height="20" viewBox="0 0 28 20" aria-hidden="true">
      <rect width="28" height="20" rx="6" fill="var(--accent)" />
      <path d="M11 5.5v9l8-4.5z" fill="#fff" />
    </svg>
    <span>YouTube Clone</span>
  </RouterLink>
</template>

<style scoped>
.logo {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
}
@media (max-width: 480px) {
  .logo span {
    display: none;
  }
}
</style>