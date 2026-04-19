function renderHealthStatus(message) {
  const element = document.getElementById('health-status');
  if (element) {
    element.textContent = message;
  }
}

function formatHealthStatus(data) {
  if (!data || typeof data !== 'object') {
    return 'API: -';
  }
  const parts = [`API: ${data.status || 'unknown'}`];
  const downloadUrl = data.download_url || 'https://ffmpeg.org/download.html';

  if (data.ffmpeg_available) {
    parts.push(`FFmpeg: ${data.ffmpeg}`);
  } else {
    parts.push(`FFmpeg: 未検出`);
    parts.push(`フォルダ指定か PATH 追加、または ${downloadUrl}`);
  }

  if (data.ffprobe_available) {
    parts.push(`FFprobe: ${data.ffprobe}`);
  } else {
    parts.push(`FFprobe: 未検出`);
  }

  if (data.available_encoder_count !== undefined) {
    parts.push(`encoders=${data.available_encoder_count}`);
  }
  return parts.join(' / ');
}

function setJobState(state) {
  const element = document.getElementById('job-state');
  if (element) {
    element.textContent = state;
  }
}

function setJobId(jobId) {
  const element = document.getElementById('job-id-label');
  if (element) {
    element.textContent = `job: ${jobId || '-'}`;
  }
}

function setProgress(progress, totalCount, completedCount, failedCount, remainingCount = 0) {
  const fill = document.getElementById('progress-fill');
  const label = document.getElementById('progress-label');
  const total = document.getElementById('total-count');
  const completed = document.getElementById('completed-count');
  const failed = document.getElementById('failed-count');
  const remaining = document.getElementById('remaining-count');

  if (fill) {
    fill.style.width = `${progress}%`;
  }
  if (label) {
    label.textContent = `${progress}%`;
  }
  if (total) {
    total.textContent = String(totalCount);
  }
  if (completed) {
    completed.textContent = String(completedCount);
  }
  if (failed) {
    failed.textContent = String(failedCount);
  }
  if (remaining) {
    remaining.textContent = String(remainingCount);
  }
}

function setCurrentFile(value) {
  const element = document.getElementById('current-file');
  if (element) {
    element.textContent = value || '-';
  }
}

function setCurrentMediaInfo(info) {
  const element = document.getElementById('current-media-info');
  if (element) {
    if (!info || Object.keys(info).length === 0) {
      element.textContent = 'probe info: -';
      return;
    }
    const parts = [];
    if (info.duration_seconds !== undefined) parts.push(`duration=${Number(info.duration_seconds).toFixed(2)}s`);
    if (info.width && info.height) parts.push(`resolution=${info.width}x${info.height}`);
    if (info.video_codec) parts.push(`video=${info.video_codec}`);
    if (info.audio_codec) parts.push(`audio=${info.audio_codec}`);
    if (info.sample_rate) parts.push(`sample_rate=${info.sample_rate}`);
    if (info.channels) parts.push(`channels=${info.channels}`);
    if (info.subtitle_stream_count !== undefined) {
      const subtitleParts = [];
      if (info.subtitle_text_stream_count) subtitleParts.push(`text=${info.subtitle_text_stream_count}`);
      if (info.subtitle_image_stream_count) subtitleParts.push(`image=${info.subtitle_image_stream_count}`);
      if (info.subtitle_other_stream_count) subtitleParts.push(`other=${info.subtitle_other_stream_count}`);
      if (subtitleParts.length) {
        parts.push(`subtitles=${info.subtitle_stream_count}(${subtitleParts.join('/')})`);
      } else {
        parts.push(`subtitles=${info.subtitle_stream_count}`);
      }
    }
    element.textContent = parts.length ? `probe info: ${parts.join(', ')}` : 'probe info: -';
  }
}

function syncAppSettingsFields(settings) {
  const source = settings && typeof settings === 'object' ? settings : {};
  const legacyPath = source.ffmpeg_path || source.ffprobe_path || '';
  setInputValue('ffmpeg-dir', source.ffmpeg_dir || legacyPath || '');
}

function collectAppSettingsFields() {
  return {
    ffmpeg_dir: getInputValue('ffmpeg-dir'),
  };
}

function setVideoSubtitleHelpText(text) {
  const element = document.getElementById('video-subtitle-help');
  if (element) {
    element.textContent = text;
  }
}

function updateVideoSubtitleGuidance(info, outputExtension = '') {
  const subtitleMode = document.getElementById('video-subtitle-mode')?.value || 'hidden';
  const extension = String(outputExtension || document.getElementById('preset-extension')?.value || '').toLowerCase();
  const hasProbeInfo = info && typeof info === 'object' && Object.keys(info).length > 0;
  const subtitleCount = Number(info?.subtitle_stream_count || 0);
  const textCount = Number(info?.subtitle_text_stream_count || 0);
  const imageCount = Number(info?.subtitle_image_stream_count || 0);
  const otherCount = Number(info?.subtitle_other_stream_count || 0);

  const baseParts = [];
  if (!hasProbeInfo) {
    baseParts.push('入力ファイルを選ぶと字幕の種類を判定します。');
  } else if (!subtitleCount) {
    baseParts.push('字幕ストリームは見つかりません。');
  } else {
    const detected = [];
    if (textCount) detected.push(`テキスト ${textCount}`);
    if (imageCount) detected.push(`画像 ${imageCount}`);
    if (otherCount) detected.push(`その他 ${otherCount}`);
    baseParts.push(`検出字幕: ${detected.join(' / ') || String(subtitleCount) + '本'}`);
  }

  if (subtitleMode === 'hidden') {
    baseParts.push('非表示を選ぶと字幕は出力されません。');
  } else if (subtitleMode === 'text') {
    if (imageCount > 0) {
      baseParts.push('テキスト字幕のみを保持します。画像字幕は自動で除外されます。MP4 ではテキスト字幕を mov_text に変換します。');
    } else if (extension === '.mp4' || extension === '.m4v' || extension === '.mov') {
      baseParts.push('テキスト字幕を mov_text に変換して保持します。画像字幕は対象外です。');
    } else {
      baseParts.push('テキスト字幕のみを保持します。画像字幕は対象外です。');
    }
  } else if (subtitleMode === 'copy') {
    if (extension === '.mp4' || extension === '.m4v' || extension === '.mov') {
      baseParts.push('画像字幕も含めて保持するのは MKV 向けです。MP4 では画像字幕を保持できません。');
    } else {
      baseParts.push('画像字幕も含めてそのまま保持します。MKV 向けです。');
    }
  }

  setVideoSubtitleHelpText(baseParts.join(' '));
}

function setVideoAudioStreamHelpText(text) {
  const element = document.getElementById('video-audio-stream-help');
  if (element) {
    element.textContent = text;
  }
}

function updateVideoAudioStreamGuidance(info) {
  const mode = document.getElementById('video-audio-stream-mode')?.value || 'all';
  const hasProbeInfo = info && typeof info === 'object' && Object.keys(info).length > 0;
  const audioCount = Number(info?.audio_stream_count || 0);
  const audioStreams = Array.isArray(info?.audio_streams) ? info.audio_streams : [];
  const audioLanguages = Array.isArray(info?.audio_stream_languages) ? info.audio_stream_languages : [];
  const japaneseCount = audioLanguages.filter((language) => {
    const normalized = String(language || '').trim().toLowerCase();
    return normalized === 'jpn' || normalized === 'ja' || normalized === 'jp' || normalized.includes('japanese');
  }).length;
  const languageList = audioStreams.length
    ? audioStreams.map((stream) => {
        const index = stream?.stream_index !== undefined ? `#${Number(stream.stream_index) + 1}` : '#?';
        const language = String(stream?.language || 'und').trim() || 'und';
        const codec = String(stream?.codec_name || '').trim();
        return codec ? `${index} ${language} (${codec})` : `${index} ${language}`;
      })
    : audioLanguages.map((language, index) => `#${index + 1} ${String(language || 'und').trim() || 'und'}`);

  if (!hasProbeInfo) {
    setVideoAudioStreamHelpText('入力ファイルを選ぶと音声トラックの種類を判定します。');
    return;
  }

  if (!audioCount) {
    setVideoAudioStreamHelpText('音声ストリームが見つかりません。');
    return;
  }

  if (mode === 'first') {
    setVideoAudioStreamHelpText('先頭の音声トラックだけを保持します。');
    return;
  }

  if (mode === 'japanese_only') {
    if (japaneseCount > 0) {
      setVideoAudioStreamHelpText(`日本語音声のみ保持します。複数ある場合は全日本語トラックを残します。検出された日本語トラック数: ${japaneseCount}。検出言語: ${languageList.join(', ')}。`);
    } else {
      setVideoAudioStreamHelpText(`日本語音声が見つかりません。全トラック保持で続行します。検出言語: ${languageList.join(', ')}。`);
    }
    return;
  }

  if (mode === 'japanese_only_first') {
    if (japaneseCount > 0) {
      setVideoAudioStreamHelpText(`日本語音声の先頭1本だけを保持します。日本語トラックが複数あっても1本だけに絞ります。検出された日本語トラック数: ${japaneseCount}。検出言語: ${languageList.join(', ')}。`);
    } else {
      setVideoAudioStreamHelpText(`日本語音声が見つかりません。全トラック保持で続行します。検出言語: ${languageList.join(', ')}。`);
    }
    return;
  }

  setVideoAudioStreamHelpText(`全音声トラックを保持します。検出トラック数: ${audioCount}。検出言語: ${languageList.join(', ')}。`);
}

function setLogLines(lines) {
  const element = document.getElementById('log-output');
  if (element) {
    element.textContent = Array.isArray(lines) && lines.length ? lines.join('\n') : 'ログなし';
    element.scrollTop = element.scrollHeight;
  }
}

function setButtonState(running) {
  const startButton = document.getElementById('start-button');
  const stopButton = document.getElementById('stop-button');
  if (startButton) {
    startButton.disabled = running;
  }
  if (stopButton) {
    stopButton.disabled = !running;
  }
}

function getSelectedType() {
  const selected = document.querySelector('input[name="type"]:checked');
  return selected ? selected.value : 'video';
}

function getInputValue(id) {
  const element = document.getElementById(id);
  return element ? element.value.trim() : '';
}

function getCheckboxValue(id) {
  const element = document.getElementById(id);
  return Boolean(element && element.checked);
}

function setCheckboxValue(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.checked = Boolean(value);
  }
}

function setCheckboxEnabled(id, enabled) {
  const element = document.getElementById(id);
  if (element) {
    element.disabled = !enabled;
  }
}

function setInputPlaceholder(value) {
  const element = document.getElementById('input-path');
  if (element) {
    element.placeholder = value;
  }
}

function setInputHelp(value) {
  const element = document.getElementById('input-help');
  if (element) {
    element.textContent = value;
  }
}

function setInputValue(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.value = value;
  }
}

function getNumberInputValue(id) {
  const raw = getInputValue(id);
  if (!raw) {
    return undefined;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function setNumberInputValue(id, value) {
  setInputValue(id, value ?? '');
}

function setInputDisabled(id, disabled) {
  const element = document.getElementById(id);
  if (element) {
    element.disabled = disabled;
  }
}

function setAudioQualityValue(value) {
  const slider = document.getElementById('audio-quality');
  const label = document.getElementById('audio-quality-value');
  const normalized = value !== undefined && value !== null && value !== '' ? String(value) : '4';
  if (slider) {
    slider.value = normalized;
  }
  if (label) {
    label.textContent = normalized;
  }
}

function setAudioQualityAutoValue(value) {
  const slider = document.getElementById('audio-quality');
  if (!slider) {
    return;
  }
  slider.dataset.userTouched = 'false';
  setAudioQualityValue(value);
}

function applyAudioQualityDefaultForSelection() {
  const slider = document.getElementById('audio-quality');
  if (!slider || slider.dataset.userTouched === 'true') {
    return;
  }
  const codec = getInputValue('audio-codec');
  const mode = document.getElementById('audio-bitrate-mode')?.value || 'cbr';
  setAudioQualityAutoValue(getDefaultAudioQuality(codec, mode));
}

function setAudioQualityHelpText(text) {
  const element = document.getElementById('audio-quality-help');
  if (element) {
    element.textContent = text;
  }
}

function getDefaultAudioQuality(codec, bitrateMode) {
  const normalizedCodec = String(codec || '').toLowerCase();
  const normalizedMode = String(bitrateMode || 'cbr').toLowerCase();
  if (normalizedMode !== 'vbr') {
    return 4;
  }
  if (normalizedCodec === 'libmp3lame') {
    return 2;
  }
  if (normalizedCodec === 'libopus') {
    return 4;
  }
  return 4;
}

function updateAudioQualityGuidance() {
  const codec = (getInputValue('audio-codec') || '').toLowerCase();
  const mode = document.getElementById('audio-bitrate-mode')?.value || 'cbr';
  if (codec === 'libopus') {
    setAudioQualityHelpText('Opus の推奨値: bitrate 96k〜128k。quality の初期値は 4 です。');
    return;
  }
  if (mode === 'vbr') {
    if (codec === 'libmp3lame') {
      setAudioQualityHelpText('MP3 VBR の推奨値: 2〜4。初期値は 2 です。0 に近いほど高品質、9 に近いほど軽量です。');
      return;
    }
    setAudioQualityHelpText('VBR の推奨値: 4 前後。0 は高品質、9 は軽量寄りです。');
    return;
  }
  setAudioQualityHelpText('CBR の推奨値: bitrate 128k〜192k。quality より bitrate が優先です。');
}

function syncVideoPresetFields(settings) {
  const source = settings && typeof settings === 'object' ? settings : {};
  const audioStreamMode = source.audio_stream_mode || 'all';
  const subtitleMode = source.subtitle_mode || 'hidden';
  const audioStreamModeElement = document.getElementById('video-audio-stream-mode');
  if (audioStreamModeElement) {
    audioStreamModeElement.value = audioStreamMode;
  }
  const subtitleModeElement = document.getElementById('video-subtitle-mode');
  if (subtitleModeElement) {
    subtitleModeElement.value = subtitleMode;
  }
  setNumberInputValue('video-threads', source.threads);
  setInputValue('video-codec', source.video_codec || '');
  setInputValue('video-preset', source.preset ?? '');
  setNumberInputValue('video-crf', source.crf);
  setNumberInputValue('video-scale-height', source.scale_height);
  setInputValue('video-audio-filter', source.audio_filter || '');
  setInputValue('video-audio-codec', source.audio_codec || '');
  setNumberInputValue('video-audio-sample-rate', source.audio_sample_rate);
  setInputValue('video-audio-bitrate', source.audio_bitrate || '');
  const audioLanguages = Array.isArray(source.audio_languages) ? source.audio_languages : [];
  const probeLanguages = Array.isArray(window.__lastProbedMediaInfo?.audio_stream_languages)
    ? window.__lastProbedMediaInfo.audio_stream_languages
    : [];
  setInputValue('video-audio-language-0', audioLanguages[0] || probeLanguages[0] || '');
  setInputValue('video-audio-language-1', audioLanguages[1] || probeLanguages[1] || '');
  setInputValue('video-audio-language-2', audioLanguages[2] || probeLanguages[2] || '');
  setInputValue('video-color-primaries', source.color_primaries || '');
  setInputValue('video-color-trc', source.color_trc || '');
  setInputValue('video-colorspace', source.colorspace || '');
  setInputValue('video-color-range', source.color_range || '');
  setInputValue('video-pix-fmt', source.pix_fmt || '');
  updateVideoSubtitleGuidance(window.__lastProbedMediaInfo || {}, document.getElementById('preset-extension')?.value || '');
  updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo || {});
}

function syncAudioPresetFields(settings) {
  const source = settings && typeof settings === 'object' ? settings : {};
  const audioMode = source.audio_mode || (source.audio_codec === 'copy' ? 'copy' : 'reencode');
  const bitrateMode = source.audio_bitrate_mode || (source.audio_quality !== undefined ? 'vbr' : 'cbr');
  const defaultQuality = getDefaultAudioQuality(source.audio_codec, bitrateMode);
  setInputValue('audio-mode', audioMode);
  setInputValue('audio-codec', source.audio_codec || '');
  setInputValue('audio-bitrate-mode', bitrateMode);
  setInputValue('audio-bitrate', source.audio_bitrate || '');
  setAudioQualityAutoValue(source.audio_quality !== undefined ? source.audio_quality : defaultQuality);
  updateAudioQualityGuidance();
  setNumberInputValue('audio-sample-rate', source.audio_sample_rate);
  setNumberInputValue('audio-channels', source.audio_channels);
  setInputValue('audio-filter', source.audio_filter || '');
  const preserveMetadata = document.getElementById('audio-preserve-metadata');
  if (preserveMetadata) {
    preserveMetadata.checked = source.preserve_metadata !== false;
  }
  const mono = document.getElementById('audio-force-mono');
  if (mono) {
    mono.checked = Boolean(source.mono);
  }
  setAudioModeUiState(audioMode, bitrateMode);
}

function syncImagePresetFields(settings) {
  const source = settings && typeof settings === 'object' ? settings : {};
  const imageMode = source.image_mode || (source.lossless ? 'lossless' : 'lossy');
  const enhanceMode = source.image_enhance_mode || ((source.image_shader_path || source.image_shader_cache || source.image_deband) ? 'enhance' : 'off');
  const preserveMetadata = source.image_preserve_metadata !== false;
  const imageExtension = String(document.getElementById('preset-extension')?.value || '').toLowerCase();
  setInputValue('image-mode', imageMode);
  setInputValue('image-enhance-mode', enhanceMode);
  setNumberInputValue('image-quality', source.quality);
  setInputValue('image-webp-preset', source.image_webp_preset || (imageExtension === '.webp' ? 'picture' : 'default'));
  setInputValue('image-jpeg-huffman', source.image_jpeg_huffman || (imageExtension === '.jpg' || imageExtension === '.jpeg' ? 'optimal' : 'default'));
  setNumberInputValue('image-compression-level', source.compression_level);
  setInputValue('image-shader-path', source.image_shader_path || '');
  setInputValue('image-shader-cache', source.image_shader_cache || '');
  setInputValue('image-upscaler', source.image_upscaler || 'spline36');
  setInputValue('image-downscaler', source.image_downscaler || 'mitchell');
  const debandElement = document.getElementById('image-deband');
  if (debandElement) {
    debandElement.checked = source.image_deband !== false;
  }
  setNumberInputValue('image-max-width', source.max_width);
  setNumberInputValue('image-max-height', source.max_height);
  const preserveMetadataElement = document.getElementById('image-preserve-metadata');
  if (preserveMetadataElement) {
    preserveMetadataElement.checked = preserveMetadata;
  }
  setImageModeUiState(imageMode);
  setImageFormatUiState(imageExtension);
  setImageEnhanceUiState(enhanceMode);
}

function collectAudioPresetFields() {
  const settings = {};
  const audioMode = document.getElementById('audio-mode')?.value || 'reencode';
  const bitrateMode = document.getElementById('audio-bitrate-mode')?.value || 'cbr';
  const audioCodec = getInputValue('audio-codec');
  const audioBitrate = getInputValue('audio-bitrate');
  const audioQuality = getNumberInputValue('audio-quality');
  const audioSampleRate = getNumberInputValue('audio-sample-rate');
  const audioChannels = getNumberInputValue('audio-channels');
  const audioFilter = getInputValue('audio-filter');
  const mono = Boolean(document.getElementById('audio-force-mono')?.checked);
  const preserveMetadata = Boolean(document.getElementById('audio-preserve-metadata')?.checked);

  if (audioMode) settings.audio_mode = audioMode;
  settings.preserve_metadata = preserveMetadata;
  if (audioMode === 'copy') {
    settings.audio_codec = 'copy';
    return settings;
  }
  if (bitrateMode) settings.audio_bitrate_mode = bitrateMode;
  if (audioCodec) settings.audio_codec = audioCodec;
  if (audioBitrate) settings.audio_bitrate = audioBitrate;
  if (audioQuality !== undefined) settings.audio_quality = Math.round(audioQuality);
  if (audioSampleRate !== undefined) settings.audio_sample_rate = audioSampleRate;
  if (audioChannels !== undefined) settings.audio_channels = audioChannels;
  if (audioFilter) settings.audio_filter = audioFilter;
  if (mono) settings.mono = true;
  return settings;
}

function syncAudioPresetSettingsTextarea() {
  const element = document.getElementById('preset-settings');
  if (!element) {
    return;
  }
  const currentText = element.value || '{}';
  let currentSettings = {};
  try {
    const parsed = JSON.parse(currentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      currentSettings = parsed;
    }
  } catch {
    currentSettings = {};
  }

  const nextSettings = collectAudioPresetFields();
  nextSettings.overwrite = Boolean(document.getElementById('preset-overwrite-existing')?.checked);
  const keys = [
    'overwrite',
    'audio_mode',
    'audio_codec',
    'audio_bitrate_mode',
    'audio_bitrate',
    'audio_quality',
    'audio_sample_rate',
    'audio_channels',
    'audio_filter',
    'mono',
    'preserve_metadata',
  ];

  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(nextSettings, key)) {
      currentSettings[key] = nextSettings[key];
    } else {
      delete currentSettings[key];
    }
  }

  element.value = JSON.stringify(currentSettings, null, 2);
}

function collectImagePresetFields() {
  const settings = {};
  const imageMode = document.getElementById('image-mode')?.value || 'lossy';
  const enhanceMode = document.getElementById('image-enhance-mode')?.value || 'off';
  const quality = getNumberInputValue('image-quality');
  const webpPreset = getInputValue('image-webp-preset');
  const jpegHuffman = getInputValue('image-jpeg-huffman');
  const compressionLevel = getNumberInputValue('image-compression-level');
  const shaderPath = getInputValue('image-shader-path');
  const shaderCache = getInputValue('image-shader-cache');
  const upscaler = getInputValue('image-upscaler');
  const downscaler = getInputValue('image-downscaler');
  const deband = Boolean(document.getElementById('image-deband')?.checked);
  const maxWidth = getNumberInputValue('image-max-width');
  const maxHeight = getNumberInputValue('image-max-height');
  const preserveMetadata = Boolean(document.getElementById('image-preserve-metadata')?.checked);

  if (imageMode) settings.image_mode = imageMode;
  if (enhanceMode) settings.image_enhance_mode = enhanceMode;
  settings.image_preserve_metadata = preserveMetadata;
  if (imageMode === 'lossless') {
    settings.lossless = true;
  }
  if (quality !== undefined) settings.quality = quality;
  if (webpPreset) settings.image_webp_preset = webpPreset;
  if (jpegHuffman) settings.image_jpeg_huffman = jpegHuffman;
  if (compressionLevel !== undefined) settings.compression_level = compressionLevel;
  if (enhanceMode === 'enhance') {
    if (shaderPath) settings.image_shader_path = shaderPath;
    if (shaderCache) settings.image_shader_cache = shaderCache;
    if (upscaler) settings.image_upscaler = upscaler;
    if (downscaler) settings.image_downscaler = downscaler;
    if (deband) settings.image_deband = true;
  }
  if (maxWidth !== undefined) settings.max_width = maxWidth;
  if (maxHeight !== undefined) settings.max_height = maxHeight;
  return settings;
}

function syncImagePresetSettingsTextarea() {
  const element = document.getElementById('preset-settings');
  if (!element) {
    return;
  }
  const currentText = element.value || '{}';
  let currentSettings = {};
  try {
    const parsed = JSON.parse(currentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      currentSettings = parsed;
    }
  } catch {
    currentSettings = {};
  }

  const nextSettings = collectImagePresetFields();
  nextSettings.overwrite = Boolean(document.getElementById('preset-overwrite-existing')?.checked);
  const keys = [
    'overwrite',
    'image_mode',
    'image_enhance_mode',
    'lossless',
    'quality',
    'image_webp_preset',
    'image_jpeg_huffman',
    'compression_level',
    'image_shader_path',
    'image_shader_cache',
    'image_upscaler',
    'image_downscaler',
    'image_deband',
    'max_width',
    'max_height',
    'image_preserve_metadata',
  ];

  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(nextSettings, key)) {
      currentSettings[key] = nextSettings[key];
    } else {
      delete currentSettings[key];
    }
  }

  element.value = JSON.stringify(currentSettings, null, 2);
}

function collectVideoPresetFields() {
  const settings = {};
  const audioStreamMode = document.getElementById('video-audio-stream-mode')?.value || 'all';
  const subtitleMode = document.getElementById('video-subtitle-mode')?.value || 'hidden';
  const threads = getNumberInputValue('video-threads');
  const videoCodec = getInputValue('video-codec');
  const preset = getInputValue('video-preset');
  const crf = getNumberInputValue('video-crf');
  const scaleHeight = getNumberInputValue('video-scale-height');
  const audioFilter = getInputValue('video-audio-filter');
  const audioCodec = getInputValue('video-audio-codec');
  const audioSampleRate = getNumberInputValue('video-audio-sample-rate');
  const audioBitrate = getInputValue('video-audio-bitrate');
  const audioLanguages = [
    getInputValue('video-audio-language-0'),
    getInputValue('video-audio-language-1'),
    getInputValue('video-audio-language-2'),
  ].map((value) => value.trim()).filter(Boolean);
  const colorPrimaries = getInputValue('video-color-primaries');
  const colorTrc = getInputValue('video-color-trc');
  const colorspace = getInputValue('video-colorspace');
  const colorRange = getInputValue('video-color-range');
  const pixFmt = getInputValue('video-pix-fmt');

  if (audioStreamMode) settings.audio_stream_mode = audioStreamMode;
  if (audioLanguages.length) settings.audio_languages = audioLanguages;
  if (subtitleMode) settings.subtitle_mode = subtitleMode;
  if (threads !== undefined) settings.threads = threads;
  if (videoCodec) settings.video_codec = videoCodec;
  if (preset) settings.preset = Number.isNaN(Number(preset)) ? preset : Number(preset);
  if (crf !== undefined) settings.crf = crf;
  if (scaleHeight !== undefined) settings.scale_height = scaleHeight;
  if (audioFilter) settings.audio_filter = audioFilter;
  if (audioCodec) settings.audio_codec = audioCodec;
  if (audioSampleRate !== undefined) settings.audio_sample_rate = audioSampleRate;
  if (audioBitrate) settings.audio_bitrate = audioBitrate;
  if (colorPrimaries) settings.color_primaries = colorPrimaries;
  if (colorTrc) settings.color_trc = colorTrc;
  if (colorspace) settings.colorspace = colorspace;
  if (colorRange) settings.color_range = colorRange;
  if (pixFmt) settings.pix_fmt = pixFmt;
  return settings;
}

function syncVideoPresetSettingsTextarea() {
  const element = document.getElementById('preset-settings');
  if (!element) {
    return;
  }
  const currentText = element.value || '{}';
  let currentSettings = {};
  try {
    const parsed = JSON.parse(currentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      currentSettings = parsed;
    }
  } catch {
    currentSettings = {};
  }

  const nextSettings = collectVideoPresetFields();
  nextSettings.overwrite = Boolean(document.getElementById('preset-overwrite-existing')?.checked);
  const keys = [
    'overwrite',
    'threads',
    'audio_stream_mode',
    'audio_languages',
    'subtitle_mode',
    'video_codec',
    'preset',
    'crf',
    'scale_height',
    'audio_filter',
    'audio_codec',
    'audio_sample_rate',
    'audio_bitrate',
    'color_primaries',
    'color_trc',
    'colorspace',
    'color_range',
    'pix_fmt',
  ];

  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(nextSettings, key)) {
      currentSettings[key] = nextSettings[key];
    } else {
      delete currentSettings[key];
    }
  }

  element.value = JSON.stringify(currentSettings, null, 2);
}

function setVideoPresetEditorVisibility(type) {
  const panel = document.getElementById('video-settings-panel');
  if (!panel) {
    return;
  }
  panel.style.display = type === 'video' ? 'block' : 'none';
  if (type === 'video') {
    updateVideoSubtitleGuidance(window.__lastProbedMediaInfo || {}, document.getElementById('preset-extension')?.value || '');
    updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo || {});
  }
}

function setAudioPresetEditorVisibility(type) {
  const panel = document.getElementById('audio-settings-panel');
  if (!panel) {
    return;
  }
  panel.style.display = type === 'audio' ? 'block' : 'none';
}

function setAudioRateControlUiState(mode) {
  const vbrMode = mode === 'vbr';
  const codec = getInputValue('audio-codec');
  const opusMode = codec === 'libopus';
  if (vbrMode) {
    setInputDisabled('audio-bitrate', !opusMode);
    setInputDisabled('audio-quality', opusMode);
  } else {
    setInputDisabled('audio-bitrate', false);
    setInputDisabled('audio-quality', true);
  }
  applyAudioQualityDefaultForSelection();
}

function setAudioModeUiState(mode, bitrateMode = 'cbr') {
  const copyMode = mode === 'copy';
  setInputDisabled('audio-codec', copyMode);
  setInputDisabled('audio-bitrate-mode', copyMode);
  setInputDisabled('audio-bitrate', copyMode);
  setInputDisabled('audio-quality', copyMode);
  setInputDisabled('audio-sample-rate', copyMode);
  setInputDisabled('audio-channels', copyMode);
  setInputDisabled('audio-filter', copyMode);
  setInputDisabled('audio-force-mono', copyMode);
  if (copyMode) {
    setInputValue('audio-codec', 'copy');
    setInputValue('audio-bitrate-mode', 'cbr');
  } else {
    setAudioRateControlUiState(bitrateMode);
  }
  updateAudioQualityGuidance();
}

function setImagePresetEditorVisibility(type) {
  const panel = document.getElementById('image-settings-panel');
  if (!panel) {
    return;
  }
  panel.style.display = type === 'image' ? 'block' : 'none';
}

function syncPresetOverwriteSetting() {
  const checkbox = document.getElementById('preset-overwrite-existing');
  const settings = document.getElementById('preset-settings');
  if (!checkbox || !settings) {
    return;
  }

  let currentSettings = {};
  try {
    const parsed = JSON.parse(settings.value || '{}');
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      currentSettings = parsed;
    }
  } catch {
    currentSettings = {};
  }

  currentSettings.overwrite = Boolean(checkbox.checked);
  settings.value = JSON.stringify(currentSettings, null, 2);
  setCheckboxValue('overwrite-existing', checkbox.checked);
}

function updateImageGuidance() {
  const mode = document.getElementById('image-mode')?.value || 'lossy';
  const enhanceMode = document.getElementById('image-enhance-mode')?.value || 'off';
  const extension = String(document.getElementById('preset-extension')?.value || '').toLowerCase();
  const qualityHelp = document.getElementById('image-quality-help');
  const webpPresetHelp = document.getElementById('image-webp-preset-help');
  const jpegHuffmanHelp = document.getElementById('image-jpeg-huffman-help');
  const enhanceHelp = document.getElementById('image-enhance-help');
  const compressionHelp = document.getElementById('image-compression-help');
  if (qualityHelp) {
    qualityHelp.textContent = mode === 'lossless'
      ? 'ロスレスでは quality は無効です。'
      : 'quality は 0-100 の目安です。WebP/JPEG の圧縮率を調整できます。';
  }
  if (webpPresetHelp) {
    webpPresetHelp.textContent = 'WebP の速度と圧縮バランスを調整します。picture / photo / drawing / icon / text が使えます。';
  }
  if (jpegHuffmanHelp) {
    jpegHuffmanHelp.textContent = 'JPEG の Huffman テーブル戦略です。optimal で容量優先、default で標準です。';
  }
  if (enhanceHelp) {
    enhanceHelp.textContent = enhanceMode === 'enhance'
      ? 'libplacebo を通します。deband と custom shader を使えます。Vulkan 対応環境向けです。'
      : '通常の画像変換です。';
  }
  if (compressionHelp) {
    if (extension === '.png') {
      compressionHelp.textContent = 'PNG は compression_level が中心です。6-9 で容量優先に寄せられます。';
    } else if (mode === 'lossless') {
      compressionHelp.textContent = 'ロスレス時は compression_level を 6-9 で試すのが目安です。';
    } else {
      compressionHelp.textContent = 'compression_level は 0-9。値が高いほど圧縮が強くなります。';
    }
  }
}

function setImageModeUiState(mode) {
  const lossless = mode === 'lossless';
  setInputDisabled('image-quality', lossless);
  setInputDisabled('image-compression-level', false);
  updateImageGuidance();
}

function setImageFormatUiState(extension) {
  const normalized = String(extension || '').toLowerCase();
  const webpGroup = document.getElementById('image-webp-preset-group');
  const jpegGroup = document.getElementById('image-jpeg-huffman-group');
  if (webpGroup) {
    webpGroup.style.display = normalized === '.webp' ? 'block' : 'none';
  }
  if (jpegGroup) {
    jpegGroup.style.display = normalized === '.jpg' || normalized === '.jpeg' ? 'block' : 'none';
  }
}

function setImageEnhanceUiState(mode) {
  const enhance = mode === 'enhance';
  setInputDisabled('image-shader-path', !enhance);
  setInputDisabled('image-shader-cache', !enhance);
  setInputDisabled('image-upscaler', !enhance);
  setInputDisabled('image-downscaler', !enhance);
  setInputDisabled('image-deband', !enhance);
  setInputDisabled('pick-shader-button', !enhance);
  setInputDisabled('clear-shader-button', !enhance);
  const help = document.getElementById('image-enhance-help');
  if (help) {
    help.textContent = enhance
      ? 'libplacebo を通した高画質化を使います。'
      : '高画質化は無効です。';
  }
  updateImageGuidance();
}

function renderTargetList(result) {
  const list = document.getElementById('target-list');
  const summary = document.getElementById('scan-summary');
  if (!list || !summary) {
    return;
  }

  const files = Array.isArray(result?.files) ? result.files : [];
  const excludedCount = Number(result?.excluded_count || 0);
  summary.textContent = `対象 ${files.length}件 / 除外 ${excludedCount}件`;

  if (!files.length) {
    list.classList.add('empty');
    list.textContent = '対象ファイルはありません。';
    return;
  }

  list.classList.remove('empty');
  list.innerHTML = '';
  const fragment = document.createDocumentFragment();
  for (const file of files) {
    const row = document.createElement('div');
    row.className = 'target-row';
    row.innerHTML = `
      <div class="target-main">
        <div class="target-name">${escapeHtml(file.relative_path || file.source_path || '')}</div>
        <div class="target-meta">${escapeHtml(file.source_path || '')}</div>
      </div>
      <div class="target-output">${escapeHtml(file.output_path || '')}</div>
    `;
    fragment.appendChild(row);
  }
  list.appendChild(fragment);
}

function renderResultList(status) {
  const list = document.getElementById('result-list');
  const summary = document.getElementById('result-summary');
  if (!list || !summary) {
    return;
  }

  const completed = Array.isArray(status?.completed_files) ? status.completed_files : [];
  const failed = Array.isArray(status?.failed_files) ? status.failed_files : [];
  const remaining = Array.isArray(status?.remaining_files) ? status.remaining_files : [];
  const all = [...completed, ...failed, ...remaining];

  summary.textContent = `完了 ${completed.length}件 / 失敗 ${failed.length}件 / 残件 ${remaining.length}件`;

  if (!all.length) {
    list.classList.add('empty');
    list.textContent = '処理結果はまだありません。';
    return;
  }

  list.classList.remove('empty');
  list.innerHTML = '';
  const fragment = document.createDocumentFragment();
  for (const file of all) {
    const row = document.createElement('div');
    row.className = `result-row result-${file.status || 'pending'}`;
    const statusLabel = file.status || 'pending';
    const sizeText = file.size_before_label && file.size_after_label
      ? `${file.size_before_label} -> ${file.size_after_label}${file.compression_ratio !== null ? ` (${file.compression_ratio}%)` : ''}`
      : `${file.size_before_label || '-'} -> ${file.size_after_label || '-'}`;
    row.innerHTML = `
      <div class="result-main">
        <div class="result-name">${escapeHtml(file.relative_path || file.source_path || '')}</div>
        <div class="result-meta">${escapeHtml(file.source_path || '')}</div>
      </div>
      <div class="result-detail">
        <div class="result-status">${escapeHtml(statusLabel)}</div>
        <div class="result-size">${escapeHtml(sizeText)}</div>
        ${file.error_message ? `<div class="result-error">${escapeHtml(file.error_message)}</div>` : ''}
      </div>
    `;
    fragment.appendChild(row);
  }
  list.appendChild(fragment);
}

function renderHistoryList(history) {
  const list = document.getElementById('history-list');
  const summary = document.getElementById('history-summary');
  if (!list || !summary) {
    return;
  }

  const items = Array.isArray(history) ? history : [];
  summary.textContent = `${items.length}件`;

  if (!items.length) {
    list.classList.add('empty');
    list.textContent = '履歴はまだありません。';
    return;
  }

  list.classList.remove('empty');
  list.innerHTML = '';
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const row = document.createElement('div');
    row.className = `history-row history-${item.state || 'pending'}`;
    row.innerHTML = `
      <div class="history-main">
        <div class="history-title">${escapeHtml(item.job_id || '')} / ${escapeHtml(item.type || '')}</div>
        <div class="history-meta">${escapeHtml(item.input_path || '')}</div>
      </div>
      <div class="history-detail">
        <div class="history-status">${escapeHtml(item.state || '')}</div>
        <div class="history-counts">完了 ${escapeHtml(item.completed_count ?? 0)} / 失敗 ${escapeHtml(item.failed_count ?? 0)} / 残件 ${escapeHtml(item.remaining_count ?? 0)}</div>
        <div class="history-output">${escapeHtml(item.output_path || '')}</div>
        <div class="history-time">${escapeHtml(item.recorded_at || '')}</div>
      </div>
    `;
    fragment.appendChild(row);
  }
  list.appendChild(fragment);
}

function getHistoryFilter() {
  const element = document.getElementById('history-filter');
  return element ? element.value : 'all';
}

function setHistoryFilter(value) {
  const element = document.getElementById('history-filter');
  if (element) {
    element.value = value;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function getPresetSelect() {
  return document.getElementById('preset-select');
}

function setPresetOptions(presets) {
  const select = getPresetSelect();
  if (!select) return;
  select.innerHTML = '';
  for (const preset of presets) {
    const option = document.createElement('option');
    option.value = preset.id;
    const sourceLabel = preset.source === 'user' ? 'user' : 'built-in';
    const defaultLabel = preset.is_default ? ' / 既定' : '';
    const unavailableLabel = preset.available === false ? ' / 未対応' : '';
    option.textContent = `${preset.name} (${sourceLabel}${defaultLabel}${unavailableLabel}) - ${preset.description}`;
    option.disabled = preset.available === false;
    select.appendChild(option);
  }
}

function getSelectedPresetId() {
  const select = getPresetSelect();
  return select ? select.value : '';
}

function setPresetEditor(preset) {
  setInputValue('preset-id', preset?.id || '');
  setInputValue('preset-name', preset?.name || '');
  setInputValue('preset-description', preset?.description || '');
  setInputValue('preset-extension', preset?.output_extension || '');
  setCheckboxValue('preset-overwrite-existing', preset?.settings?.overwrite);
  setCheckboxValue('overwrite-existing', preset?.settings?.overwrite);
  const settings = document.getElementById('preset-settings');
  const template = document.getElementById('preset-template');
  if (settings) {
    settings.value = JSON.stringify(preset?.settings || {}, null, 2);
  }
  if (template) {
    template.value = JSON.stringify(preset?.ffmpeg_args_template || [], null, 2);
  }
  const type = getSelectedType();
  setVideoPresetEditorVisibility(type);
  setAudioPresetEditorVisibility(type);
  setImagePresetEditorVisibility(type);
  if (type === 'video') {
    syncVideoPresetFields(preset?.settings || {});
    syncVideoPresetSettingsTextarea();
  } else if (type === 'audio') {
    syncAudioPresetFields(preset?.settings || {});
    syncAudioPresetSettingsTextarea();
  } else if (type === 'image') {
    syncImagePresetFields(preset?.settings || {});
    syncImagePresetSettingsTextarea();
  } else {
    syncVideoPresetFields({});
    syncAudioPresetFields({});
    syncImagePresetFields({});
  }
}

function getPresetEditor() {
  const settingsText = document.getElementById('preset-settings')?.value || '{}';
  const templateText = document.getElementById('preset-template')?.value || '[]';
  return {
    id: getInputValue('preset-id'),
    name: getInputValue('preset-name'),
    description: getInputValue('preset-description'),
    output_extension: getInputValue('preset-extension'),
    settings: JSON.parse(settingsText),
    ffmpeg_args_template: JSON.parse(templateText),
  };
}
