<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { copyText } from '../composables/clipboard'
import { formatDuration, formatRelative, formatViews } from '../composables/format'
import { useAuth } from '../composables/useAuth'
import AppIcon from './AppIcon.vue'
import ReportDialog from './ReportDialog.vue'
import SavePlaylistDialog from './SavePlaylistDialog.vue'

const props = defineProps({
  video: { type: Object, required: true },
  horizontal: Boolean,
  compact: Boolean,
  removeLabel: { type: String, default: '' },
  hideWatchLater: Boolean,
})
const emit = defineEmits(['remove'])

const route = useRoute()
const router = useRouter()
const { state: auth } = useAuth()

const menuOpen = ref(false)
const saveOpen = ref(false)
const reportOpen = ref(false)
const note = ref('')
let noteTimer = null

// Сервер всё равно проверит: это только чтобы не показывать пункт, который заведомо откажет
const isOwn = computed(() => auth.user?.channel.id === props.video.channel.id)

onBeforeUnmount(() => clearTimeout(noteTimer))

function say(text) {
  note.value = text
  clearTimeout(noteTimer)
  noteTimer = setTimeout(() => (note.value = ''), 2500)
}

function requireLogin() {
  if (auth.user) return true
  router.push({ name: 'login', query: { next: route.fullPath } })
  return false
}

async function watchLater() {
  menuOpen.value = false
  if (!requireLogin()) return
  try {
    await api.playlists.addToWatchLater(props.video.id)
    say('Добавлено в «Смотреть позже»')
  } catch (e) {
    say(e.message)
  }
}

function addToPlaylist() {
  menuOpen.value = false
  if (requireLogin()) saveOpen.value = true
}

async function share() {
  menuOpen.value = false
  const ok = await copyText(`${location.origin}/watch/${props.video.id}`)
  say(ok ? 'Ссылка скопирована' : 'Не удалось скопировать ссылку')
}

function removeItem() {
  menuOpen.value = false
  emit('remove', props.video)
}

function report() {
  menuOpen.value = false
  if (requireLogin()) reportOpen.value = true
}
</script>

<template>
  <article class="card" :class="{ horizontal, compact, 'menu-open': menuOpen }">
    <RouterLink :to="`/watch/${video.id}`" class="thumb">
      <img :src="`/api/videos/${video.id}/thumbnail`" :alt="video.title" loading="lazy" />
      <span class="duration">{{ formatDuration(video.duration_seconds) }}</span>
    </RouterLink>
    <div class="info">
      <RouterLink
        :to="`/@${video.channel.handle}`"
        class="avatar"
        :aria-label="video.channel.name"
      >
        {{ video.channel.name[0]?.toUpperCase() }}
      </RouterLink>
      <div class="text">
        <RouterLink :to="`/watch/${video.id}`" class="title">{{ video.title }}</RouterLink>
        <RouterLink :to="`/@${video.channel.handle}`" class="channel">
          {{ video.channel.name }}
        </RouterLink>
        <div class="muted">
          {{ formatViews(video.views_count) }} • {{ formatRelative(video.created_at) }}
        </div>
        <div v-if="note" class="note" role="status">{{ note }}</div>
      </div>

      <div class="menu-wrap">
        <button
          type="button"
          class="icon-btn burger"
          aria-label="Действия"
          aria-haspopup="true"
          @click="menuOpen = !menuOpen"
        >
          <AppIcon name="more" />
        </button>
        <div v-if="menuOpen" class="backdrop" @click="menuOpen = false" />
        <div v-if="menuOpen" class="menu" role="menu">
          <button v-if="!props.hideWatchLater" type="button" role="menuitem" class="item" @click="watchLater">
            <AppIcon name="watchLater" :size="22" />
            <span>Смотреть позже</span>
          </button>
          <button type="button" role="menuitem" class="item" @click="addToPlaylist">
            <AppIcon name="playlistAdd" :size="22" />
            <span>Добавить в плейлист</span>
          </button>
          <button type="button" role="menuitem" class="item" @click="share">
            <AppIcon name="share" :size="22" />
            <span>Поделиться</span>
          </button>
          <button v-if="!isOwn" type="button" role="menuitem" class="item" @click="report">
            <AppIcon name="flag" :size="22" />
            <span>Пожаловаться</span>
          </button>
          <button v-if="removeLabel" type="button" role="menuitem" class="item" @click="removeItem">
            <AppIcon name="delete" :size="22" />
            <span>{{ removeLabel }}</span>
          </button>
        </div>
      </div>
    </div>

    <SavePlaylistDialog v-if="saveOpen" :video-id="video.id" @close="saveOpen = false" />
    <ReportDialog
      v-if="reportOpen"
      kind="video"
      :target-id="video.id"
      @close="reportOpen = false"
    />
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.thumb {
  position: relative;
  display: block;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--surface);
}
.thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card.menu-open {
  z-index: 100;
}
.duration {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}
.info {
  display: flex;
  flex: 1;
  gap: 12px;
  min-width: 0;
  margin-bottom: auto;
}
.avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-weight: 500;
}
.text {
  flex: 1;
  min-width: 0;
}
.title {
  display: -webkit-box;
  margin-bottom: 4px;
  overflow: hidden;
  color: var(--text);
  font-size: 16px;
  font-weight: 500;
  line-height: 1.3;
  overflow-wrap: anywhere;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.channel {
  display: block;
  color: var(--text-secondary);
}
.channel:hover {
  color: var(--text);
}
.note {
  margin-top: 4px;
  color: var(--link);
}
.menu-wrap {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 12;
}
.horizontal {
  position: relative;
}
.horizontal .text {
  padding-right: 32px;
}
.burger {
  width: 32px;
  height: 32px;
  margin-right: -8px;
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 10;
}
.menu {
  position: absolute;
  right: 0;
  top: 36px;
  z-index: 20;
  min-width: 240px;
  padding: 8px 0;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4);
}
.item {
  display: flex;
  gap: 16px;
  align-items: center;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.item:hover {
  background: var(--surface-hover);
}
.horizontal,
.compact {
  flex-direction: row;
}
.horizontal .avatar,
.compact .avatar {
  display: none;
}
.horizontal .thumb {
  flex: 0 0 360px;
  max-width: 45%;
}
.compact {
  gap: 8px;
}
.compact .thumb {
  flex: 0 0 168px;
}
.compact .title {
  font-size: 14px;
}
.compact .info {
  font-size: 12px;
}
@media (max-width: 600px) {
  .horizontal {
    flex-direction: column;
  }
  .horizontal .thumb {
    flex: none;
    max-width: none;
  }
}
</style>