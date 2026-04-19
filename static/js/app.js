let activeJobId = '';
let pollTimer = null;
let loadedPresets = [];
window.__lastProbedMediaInfo = {};

function getLoadedPresetById(presetId) {
  return loadedPresets.find((preset) => preset.id === presetId) || null;
}

function isPresetSelectable(preset) {
  return preset && preset.available !== false;
}

function getPreferredImagePresetId() {
  const extension = String(document.getElementById('preset-extension')?.value || '').toLowerCase();
  if (extension === '.jpg' || extension === '.jpeg') {
    return 'image_jpeg_standard';
  }
  if (extension === '.png') {
    return 'image_png_high_compress';
  }
  if (extension === '.webp') {
    return 'image_webp_photo';
  }
  return 'image_webp_photo';
}

async function loadPresetsForType(type) {
  loadedPresets = await fetchPresets(type);
  const selectedPresetId = getSelectedPresetId();
  setPresetOptions(loadedPresets);
  const selectablePresets = loadedPresets.filter(isPresetSelectable);
  const defaultPreset = selectablePresets.find((preset) => preset.is_default) || null;
  const preferredImagePreset = type === 'image' ? selectablePresets.find((preset) => preset.id === getPreferredImagePresetId()) || null : null;
  const nextSelected = selectablePresets.find((preset) => preset.id === selectedPresetId) || preferredImagePreset || defaultPreset || selectablePresets[0] || loadedPresets[0] || null;
  if (nextSelected) {
    const select = document.getElementById('preset-select');
    if (select) {
      select.value = nextSelected.id;
    }
    setPresetEditor(nextSelected);
  } else {
    setPresetEditor(null);
  }
}

function syncModeUi() {
  const mode = getInputValue('input-mode');
  const fileMode = mode === 'file';
  setCheckboxEnabled('include-subfolders', !fileMode);
  setCheckboxEnabled('keep-folder-structure', !fileMode);
  if (fileMode) {
    const includeSubfolders = document.getElementById('include-subfolders');
    const keepFolderStructure = document.getElementById('keep-folder-structure');
    if (includeSubfolders) includeSubfolders.checked = false;
    if (keepFolderStructure) keepFolderStructure.checked = false;
    setInputPlaceholder('C:\\input\\sample.mp4');
    setInputHelp('ローカルPC上の単一ファイルパスを入力してください。');
  } else {
    setInputPlaceholder('C:\\input\\folder');
    setInputHelp('ローカルPC上のフォルダパスを入力してください。');
  }
}

async function handlePickInput() {
  const mode = getInputValue('input-mode');
  const type = getSelectedType();

  try {
    const path = mode === 'folder' ? await pickInputFolder() : await pickInputFile(type);
    setInputValue('input-path', path);
    if (mode === 'file' && type === 'video' && path) {
      try {
        const probe = await probeMedia(path);
        window.__lastProbedMediaInfo = probe.media_info || {};
        setCurrentMediaInfo(window.__lastProbedMediaInfo);
        updateVideoSubtitleGuidance(window.__lastProbedMediaInfo, getInputValue('preset-extension'));
        updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo);
      } catch (probeError) {
        window.__lastProbedMediaInfo = {};
        setCurrentMediaInfo({});
        updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
        updateVideoAudioStreamGuidance({});
        setLogLines([`字幕情報取得失敗: ${probeError.message}`]);
      }
    }
  } catch (error) {
    setLogLines([`選択失敗: ${error.message}`]);
  }
}

async function handleProbeInputPath() {
  const mode = getInputValue('input-mode');
  const type = getSelectedType();
  const path = getInputValue('input-path');
  if (mode !== 'file' || type !== 'video' || !path) {
    window.__lastProbedMediaInfo = {};
    setCurrentMediaInfo({});
    updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
    updateVideoAudioStreamGuidance({});
    return;
  }
  try {
    const probe = await probeMedia(path);
    window.__lastProbedMediaInfo = probe.media_info || {};
    setCurrentMediaInfo(window.__lastProbedMediaInfo);
    updateVideoSubtitleGuidance(window.__lastProbedMediaInfo, getInputValue('preset-extension'));
    updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo);
  } catch (error) {
    window.__lastProbedMediaInfo = {};
    setCurrentMediaInfo({});
    updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
    updateVideoAudioStreamGuidance({});
  }
}

async function handlePickOutput() {
  try {
    const path = await pickInputFolder();
    setInputValue('output-path', path);
  } catch (error) {
    setLogLines([`保存先選択失敗: ${error.message}`]);
  }
}

async function handlePickShader() {
  try {
    const path = await pickShaderFile();
    setInputValue('image-shader-path', path);
    syncImagePresetSettingsTextarea();
  } catch (error) {
    setLogLines([`shader選択失敗: ${error.message}`]);
  }
}

function handleClearShader() {
  setInputValue('image-shader-path', '');
  syncImagePresetSettingsTextarea();
}

function refreshPresetEditorFromSelection() {
  const preset = getLoadedPresetById(getSelectedPresetId());
  if (preset) {
    setPresetEditor(preset);
  }
}

async function handleSavePreset() {
  const type = getSelectedType();
  try {
    const preset = getPresetEditor();
    await savePreset({ type, preset });
    await loadPresetsForType(type);
    setLogLines(['プリセットを保存しました。']);
  } catch (error) {
    setLogLines([`保存失敗: ${error.message}`]);
  }
}

async function loadAppSettings() {
  const response = await getAppSettings();
  syncAppSettingsFields(response.settings);
}

async function handleSaveAppSettings() {
  try {
    const payload = collectAppSettingsFields();
    const result = await saveAppSettings(payload);
    syncAppSettingsFields(payload);
    await refreshHealth();
    await loadPresetsForType(getSelectedType());
    setLogLines([result.message || 'FFmpeg フォルダ設定を保存しました。']);
  } catch (error) {
    setLogLines([`FFmpeg フォルダ設定保存失敗: ${error.message}`]);
  }
}

async function handleSavePresetAsDefault() {
  const type = getSelectedType();
  try {
    const preset = getPresetEditor();
    await savePresetAsDefault({ type, preset });
    await loadPresetsForType(type);
    setLogLines(['プリセットを保存して既定に設定しました。']);
  } catch (error) {
    setLogLines([`既定設定失敗: ${error.message}`]);
  }
}

async function handleClearPresetDefault() {
  const type = getSelectedType();
  try {
    await clearDefaultPreset({ type });
    await loadPresetsForType(type);
    setLogLines(['既定を解除しました。']);
  } catch (error) {
    setLogLines([`既定解除失敗: ${error.message}`]);
  }
}

async function handleDeletePreset() {
  const type = getSelectedType();
  const presetId = getSelectedPresetId();
  if (!presetId) {
    setLogLines(['削除対象がありません。']);
    return;
  }
  try {
    await deletePreset({ type, preset_id: presetId });
    await loadPresetsForType(type);
    setLogLines(['プリセットを削除しました。']);
  } catch (error) {
    setLogLines([`削除失敗: ${error.message}`]);
  }
}

async function handleRestorePresetDefaults() {
  const type = getSelectedType();
  try {
    await restorePresetDefaults({ type });
    await loadPresetsForType(type);
    setLogLines(['初期プリセットに戻しました。']);
  } catch (error) {
    setLogLines([`初期化失敗: ${error.message}`]);
  }
}

async function handleScanTargets() {
  const payload = {
    type: getSelectedType(),
    input_mode: getInputValue('input-mode'),
    input_path: getInputValue('input-path'),
    include_subfolders: getCheckboxValue('include-subfolders'),
  };

  try {
    const result = await scanTargets(payload);
    renderTargetList(result);
    setLogLines([`スキャン完了: ${result.count}件 / 除外 ${result.excluded_count}件`]);
  } catch (error) {
    setLogLines([`スキャン失敗: ${error.message}`]);
  }
}

async function handleOpenOutput() {
  const path = getInputValue('output-path');
  try {
    const result = await openOutputPath(path);
    setLogLines([result.message || '保存先を開きました。']);
  } catch (error) {
    setLogLines([`保存先オープン失敗: ${error.message}`]);
  }
}

async function refreshHistory() {
  try {
    const state = getHistoryFilter();
    const history = await fetchHistory(20, state);
    renderHistoryList(history);
  } catch (error) {
    setLogLines([`履歴取得失敗: ${error.message}`]);
  }
}

async function handleExportConfig() {
  try {
    const data = await exportConfig();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'browser_ffmpeg_config.json';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setLogLines(['設定を書き出しました。']);
  } catch (error) {
    setLogLines([`書き出し失敗: ${error.message}`]);
  }
}

async function handleImportConfigFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) {
    return;
  }
  try {
    const text = await file.text();
    const payload = JSON.parse(text);
    await importConfig(payload);
    await loadAppSettings();
    await loadPresetsForType(getSelectedType());
    await refreshHealth();
    setLogLines(['設定を読み込みました。']);
  } catch (error) {
    setLogLines([`読み込み失敗: ${error.message}`]);
  } finally {
    event.target.value = '';
  }
}

async function refreshHealth() {
  try {
    const data = await getHealthStatus();
    renderHealthStatus(formatHealthStatus(data));
  } catch (error) {
    renderHealthStatus(`API確認失敗: ${error.message}`);
  }
}

async function handleStart() {
  const outputPath = getInputValue('output-path') || 'temp\\out';
  const payload = {
    type: getSelectedType(),
    input_mode: getInputValue('input-mode'),
    input_path: getInputValue('input-path'),
    include_subfolders: getCheckboxValue('include-subfolders'),
    output_path: outputPath,
    keep_folder_structure: getCheckboxValue('keep-folder-structure'),
    overwrite: getCheckboxValue('overwrite-existing'),
    preset_id: getSelectedPresetId(),
  };

  try {
    const result = await startJob(payload);
    activeJobId = result.job_id;
    setJobId(activeJobId);
    setJobState(result.state);
    setButtonState(true);
    setLogLines(['ジョブ開始']);
    startPolling();
  } catch (error) {
    setLogLines([`開始失敗: ${error.message}`]);
  }
}

async function handleStop() {
  if (!activeJobId) {
    return;
  }
  try {
    await stopJob(activeJobId);
  } catch (error) {
    setLogLines([`停止失敗: ${error.message}`]);
  }
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (!activeJobId) {
      return;
    }
    try {
      const status = await fetchJobStatus(activeJobId);
      setJobState(status.state);
      setProgress(
        status.progress_percent,
        status.total_count,
        status.completed_count,
        status.failed_count,
        status.remaining_count || 0,
      );
      setCurrentFile(status.current_file);
      setCurrentMediaInfo(status.current_media_info);
      renderResultList(status);
      setLogLines(status.last_log_lines);
      if (status.state === 'completed' || status.state === 'failed' || status.state === 'stopped') {
        setButtonState(false);
        stopPolling();
        await refreshHistory();
      }
    } catch (error) {
      setLogLines([`状態取得失敗: ${error.message}`]);
      setButtonState(false);
      stopPolling();
    }
  }, 500);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadAppSettings();
  } catch (error) {
    setLogLines([`FFmpeg フォルダ設定読込失敗: ${error.message}`]);
  }
  await refreshHealth();

  try {
    await loadPresetsForType(getSelectedType());
    await refreshHistory();
  } catch (error) {
    setLogLines([`プリセット読込失敗: ${error.message}`]);
  }

  syncModeUi();
  setVideoPresetEditorVisibility(getSelectedType());
  setAudioPresetEditorVisibility(getSelectedType());
  setImagePresetEditorVisibility(getSelectedType());

  const outputPath = document.getElementById('output-path');
  if (outputPath && !outputPath.value.trim()) {
    outputPath.value = 'temp\\out';
  }

  document.querySelectorAll('input[name="type"]').forEach((input) => {
    input.addEventListener('change', async () => {
      try {
        await loadPresetsForType(getSelectedType());
        setVideoPresetEditorVisibility(getSelectedType());
        setAudioPresetEditorVisibility(getSelectedType());
        setImagePresetEditorVisibility(getSelectedType());
        window.__lastProbedMediaInfo = {};
        setCurrentMediaInfo({});
        updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
        updateVideoAudioStreamGuidance({});
        await handleProbeInputPath();
      } catch (error) {
        setLogLines([`プリセット読込失敗: ${error.message}`]);
      }
    });
  });

  const inputMode = document.getElementById('input-mode');
  if (inputMode) {
    inputMode.addEventListener('change', () => {
      syncModeUi();
      window.__lastProbedMediaInfo = {};
      setCurrentMediaInfo({});
      updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
      updateVideoAudioStreamGuidance({});
      handleProbeInputPath();
    });
  }

  const inputPath = document.getElementById('input-path');
  if (inputPath) {
    inputPath.addEventListener('change', handleProbeInputPath);
  }

  const presetSelect = document.getElementById('preset-select');
  if (presetSelect) {
    presetSelect.addEventListener('change', refreshPresetEditorFromSelection);
  }

  const presetOverwrite = document.getElementById('preset-overwrite-existing');
  if (presetOverwrite) {
    presetOverwrite.addEventListener('change', syncPresetOverwriteSetting);
  }

  const videoFieldIds = [
    'video-audio-stream-mode',
    'video-audio-language-0',
    'video-audio-language-1',
    'video-audio-language-2',
    'video-subtitle-mode',
    'video-threads',
    'video-codec',
    'video-preset',
    'video-crf',
    'video-scale-height',
    'video-audio-filter',
    'video-audio-codec',
    'video-audio-sample-rate',
    'video-audio-bitrate',
    'video-color-primaries',
    'video-color-trc',
    'video-colorspace',
    'video-color-range',
    'video-pix-fmt',
  ];
  videoFieldIds.forEach((id) => {
    const element = document.getElementById(id);
    if (element) {
      const handler = element.tagName === 'SELECT' ? 'change' : 'input';
      if (id === 'video-audio-stream-mode') {
        element.addEventListener('change', () => {
          syncVideoPresetSettingsTextarea();
          updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo || {});
        });
      } else {
        element.addEventListener(handler, syncVideoPresetSettingsTextarea);
        element.addEventListener('change', syncVideoPresetSettingsTextarea);
      }
    }
  });

  const audioFieldIds = [
    'audio-mode',
    'audio-codec',
    'audio-bitrate-mode',
    'audio-bitrate',
    'audio-quality',
    'audio-sample-rate',
    'audio-channels',
    'audio-filter',
    'audio-force-mono',
    'audio-preserve-metadata',
  ];
  audioFieldIds.forEach((id) => {
    const element = document.getElementById(id);
    if (element) {
      const handler = element.tagName === 'SELECT' || element.type === 'checkbox' ? 'change' : 'input';
      if (id === 'audio-mode') {
        element.addEventListener('change', () => {
          setAudioModeUiState(element.value, document.getElementById('audio-bitrate-mode')?.value || 'cbr');
          updateAudioQualityGuidance();
          syncAudioPresetSettingsTextarea();
        });
      } else if (id === 'audio-bitrate-mode') {
        element.addEventListener('change', () => {
          setAudioRateControlUiState(element.value);
          updateAudioQualityGuidance();
          syncAudioPresetSettingsTextarea();
        });
      } else if (id === 'audio-codec') {
        element.addEventListener('input', () => {
          setAudioRateControlUiState(document.getElementById('audio-bitrate-mode')?.value || 'cbr');
          updateAudioQualityGuidance();
          syncAudioPresetSettingsTextarea();
        });
      } else if (id === 'audio-quality') {
        element.addEventListener('input', () => {
          element.dataset.userTouched = 'true';
          setAudioQualityValue(element.value);
          syncAudioPresetSettingsTextarea();
        });
      } else {
        element.addEventListener(handler, syncAudioPresetSettingsTextarea);
        element.addEventListener('change', syncAudioPresetSettingsTextarea);
      }
    }
  });

  const imageFieldIds = [
    'image-mode',
    'image-enhance-mode',
    'image-quality',
    'image-webp-preset',
    'image-jpeg-huffman',
    'image-compression-level',
    'image-shader-path',
    'image-shader-cache',
    'image-upscaler',
    'image-downscaler',
    'image-deband',
    'image-max-width',
    'image-max-height',
    'image-preserve-metadata',
  ];
  imageFieldIds.forEach((id) => {
    const element = document.getElementById(id);
    if (!element) {
      return;
    }
    if (id === 'image-mode') {
      element.addEventListener('change', () => {
        setImageModeUiState(element.value);
        syncImagePresetSettingsTextarea();
      });
      return;
    }
    if (id === 'image-enhance-mode') {
      element.addEventListener('change', () => {
        setImageEnhanceUiState(element.value);
        syncImagePresetSettingsTextarea();
      });
      return;
    }
    const handler = element.tagName === 'SELECT' || element.type === 'checkbox' ? 'change' : 'input';
    element.addEventListener(handler, syncImagePresetSettingsTextarea);
    element.addEventListener('change', syncImagePresetSettingsTextarea);
  });

  const presetExtension = document.getElementById('preset-extension');
  if (presetExtension) {
    const updateFormatState = () => {
      setImageFormatUiState(presetExtension.value);
      updateVideoSubtitleGuidance(window.__lastProbedMediaInfo || {}, presetExtension.value);
      updateVideoAudioStreamGuidance(window.__lastProbedMediaInfo || {});
    };
    presetExtension.addEventListener('input', updateFormatState);
    presetExtension.addEventListener('change', updateFormatState);
  }

  const startButton = document.getElementById('start-button');
  if (startButton) {
    startButton.addEventListener('click', handleStart);
  }

  const pickButton = document.getElementById('pick-input-button');
  if (pickButton) {
    pickButton.addEventListener('click', handlePickInput);
  }

  const scanButton = document.getElementById('scan-button');
  if (scanButton) {
    scanButton.addEventListener('click', handleScanTargets);
  }

  const stopButton = document.getElementById('stop-button');
  if (stopButton) {
    stopButton.addEventListener('click', handleStop);
  }

  const refreshButton = document.getElementById('refresh-presets-button');
  if (refreshButton) {
    refreshButton.addEventListener('click', async () => {
      try {
        await loadPresetsForType(getSelectedType());
      } catch (error) {
        setLogLines([`プリセット更新失敗: ${error.message}`]);
      }
    });
  }

  const openOutputButton = document.getElementById('open-output-button');
  if (openOutputButton) {
    openOutputButton.addEventListener('click', handleOpenOutput);
  }

  const saveAppSettingsButton = document.getElementById('save-app-settings-button');
  if (saveAppSettingsButton) {
    saveAppSettingsButton.addEventListener('click', handleSaveAppSettings);
  }

  const pickOutputButton = document.getElementById('pick-output-button');
  if (pickOutputButton) {
    pickOutputButton.addEventListener('click', handlePickOutput);
  }

  const pickShaderButton = document.getElementById('pick-shader-button');
  if (pickShaderButton) {
    pickShaderButton.addEventListener('click', handlePickShader);
  }

  const clearShaderButton = document.getElementById('clear-shader-button');
  if (clearShaderButton) {
    clearShaderButton.addEventListener('click', handleClearShader);
  }

  const subtitleMode = document.getElementById('video-subtitle-mode');
  if (subtitleMode) {
    subtitleMode.addEventListener('change', () => {
      updateVideoSubtitleGuidance(window.__lastProbedMediaInfo || {}, getInputValue('preset-extension'));
    });
  }

  const exportConfigButton = document.getElementById('export-config-button');
  if (exportConfigButton) {
    exportConfigButton.addEventListener('click', handleExportConfig);
  }

  const importConfigButton = document.getElementById('import-config-button');
  const importConfigFile = document.getElementById('import-config-file');
  if (importConfigButton && importConfigFile) {
    importConfigButton.addEventListener('click', () => importConfigFile.click());
    importConfigFile.addEventListener('change', handleImportConfigFile);
  }

  const savePresetButton = document.getElementById('save-preset-button');
  if (savePresetButton) {
    savePresetButton.addEventListener('click', handleSavePreset);
  }

  const savePresetDefaultButton = document.getElementById('save-preset-default-button');
  if (savePresetDefaultButton) {
    savePresetDefaultButton.addEventListener('click', handleSavePresetAsDefault);
  }

  const clearPresetDefaultButton = document.getElementById('clear-preset-default-button');
  if (clearPresetDefaultButton) {
    clearPresetDefaultButton.addEventListener('click', handleClearPresetDefault);
  }

  const deletePresetButton = document.getElementById('delete-preset-button');
  if (deletePresetButton) {
    deletePresetButton.addEventListener('click', handleDeletePreset);
  }

  const restorePresetButton = document.getElementById('restore-preset-button');
  if (restorePresetButton) {
    restorePresetButton.addEventListener('click', handleRestorePresetDefaults);
  }

  const historyFilter = document.getElementById('history-filter');
  if (historyFilter) {
    historyFilter.addEventListener('change', refreshHistory);
  }

  setButtonState(false);
  setProgress(0, 0, 0, 0);
  setCurrentFile('-');
  setCurrentMediaInfo(null);
  updateVideoSubtitleGuidance({}, getInputValue('preset-extension'));
  setJobState('idle');
});
