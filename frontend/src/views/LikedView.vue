<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import PlaylistSidePanel from '../components/PlaylistSidePanel.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const playlist = ref(null)
const loadError = ref('')
const { items, loading, done, error, loadMore } = usePagedList((cursor) =>
  api.playlists.likedVideos(cursor),
)

onMounted(async () => {
  document.title = 'Понравившиеся — YouTube Clone'
  try {
    playlist.value = await api.playlists.liked()
  } catch (e) {
    loadError.value = e.message
  }
})
</script>

<template>
  <div class="liked">
    <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>
    <div class="side"><PlaylistSidePanel v-if="playlist" :playlist="playlist" /></div>
    <div class="list">
      <VideoCard v-for="video in items" :key="video.id" :video="video" horizontal />
      <p v-if="done && !items.length" class="muted">Здесь пока ничего нет</p>
      <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
    </div>
  </div>
</template>

<style scoped>
.liked {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.side {
  position: sticky;
  top: calc(var(--header-height) + 24px);
  flex: 0 0 360px;
  width: 360px;
}
.list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
@media (max-width: 900px) {
  .liked {
    flex-direction: column;
    align-items: stretch;
    padding: 16px 12px;
  }
  .side {
    position: static;
    flex: none;
    width: auto;
  }
}
</style>