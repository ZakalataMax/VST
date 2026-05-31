import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  IconButton,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ContentPasteIcon from '@mui/icons-material/ContentPaste';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import { formatNumbers, formatNumbersWithQuotes, getTrimmedLines } from './formatter';
import { analyzeDuplicates, formatDuplicateReport } from './duplicates';

const placeholderSx = {
  '& .MuiInputBase-input::placeholder': {
    color: 'rgba(158, 158, 158, 0.65)',
    opacity: 0.45,
  },
  '& .MuiInputBase-input.MuiInputBase-inputMultiline::placeholder': {
    color: 'rgba(158, 158, 158, 0.65)',
    opacity: 0.45,
  },
};

const fieldActionSx = {
  position: 'absolute',
  top: 8,
  right: 8,
  zIndex: 3,
  backgroundColor: 'rgba(15, 17, 21, 0.65)',
  border: '1px solid rgba(255,255,255,0.08)',
  '&:hover': {
    backgroundColor: 'rgba(15, 17, 21, 0.9)',
  },
};

const fieldActionSecondarySx = {
  ...fieldActionSx,
  right: 44,
  color: 'rgba(255, 107, 107, 0.7)',
  backgroundColor: 'rgba(244, 67, 54, 0.07)',
  border: '1px solid rgba(244, 67, 54, 0.3)',
  boxShadow: 'inset 0 0 0 1px rgba(244, 67, 54, 0.08)',
  '& .MuiSvgIcon-root': {
    color: 'rgba(255, 107, 107, 0.7)',
  },
  '&:hover': {
    backgroundColor: 'rgba(244, 67, 54, 0.11)',
    border: '1px solid rgba(244, 67, 54, 0.45)',
  },
};

const copyText = async text => {
  if (!text) {
    return false;
  }

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const area = document.createElement('textarea');
  area.value = text;
  document.body.appendChild(area);
  area.select();
  document.execCommand('copy');
  document.body.removeChild(area);
  return true;
};

export default function ParsingToolsPage() {
  const [formatterInput, setFormatterInput] = useState('');
  const [formatterOutput, setFormatterOutput] = useState('');
  const [formatterMode, setFormatterMode] = useState('plain');
  const [duplicatesInput, setDuplicatesInput] = useState('');
  const [duplicatesOutput, setDuplicatesOutput] = useState('');
  const [splitterInput, setSplitterInput] = useState('');
  const [splitPattern, setSplitPattern] = useState('1000,1000,500');
  const [splitBlocks, setSplitBlocks] = useState([]);
  const [alertText, setAlertText] = useState('');

  const formatterLinesCount = useMemo(() => getTrimmedLines(formatterInput).length, [formatterInput]);
  const duplicatesLinesCount = useMemo(() => getTrimmedLines(duplicatesInput).length, [duplicatesInput]);
  const splitterLinesCount = useMemo(() => getTrimmedLines(splitterInput).length, [splitterInput]);
  const formatterPlaceholder = formatterMode === 'quoted' ? "Example:\n'123','456','789'" : 'Example:\n123, 456, 789';

  const showAlert = text => setAlertText(text);

  const handlePaste = async type => {
    try {
      const text = await navigator.clipboard.readText();
      if (type === 'formatter') {
        setFormatterInput(text);
      } else if (type === 'duplicates') {
        setDuplicatesInput(text);
      } else {
        setSplitterInput(text);
      }
      showAlert('Text pasted from clipboard.');
    } catch {
      showAlert('Clipboard paste is not available in this browser.');
    }
  };

  useEffect(() => {
    const result = formatterMode === 'quoted' ? formatNumbersWithQuotes(formatterInput) : formatNumbers(formatterInput);
    setFormatterOutput(result);
  }, [formatterInput, formatterMode]);

  useEffect(() => {
    const lines = getTrimmedLines(duplicatesInput);
    if (lines.length === 0) {
      setDuplicatesOutput('');
      return;
    }
    const analysis = analyzeDuplicates(duplicatesInput);
    const report = formatDuplicateReport(analysis);
    setDuplicatesOutput(report);
  }, [duplicatesInput]);

  const handleCopy = async (text, emptyMessage) => {
    if (!text) {
      showAlert(emptyMessage);
      return;
    }
    try {
      await copyText(text);
      showAlert('Result copied.');
    } catch {
      showAlert('Copy failed.');
    }
  };

  const handleSplitIntoBlocks = () => {
    const lines = getTrimmedLines(splitterInput);
    if (lines.length === 0) {
      setSplitBlocks([]);
      showAlert('Nothing to split. Paste lines first.');
      return;
    }
    const rawParts = splitPattern
      .split(/[,;\s]+/)
      .map(s => s.trim())
      .filter(Boolean);
    if (rawParts.length === 0) {
      setSplitBlocks([]);
      showAlert('Enter block sizes, e.g. 1000, 1000, 500.');
      return;
    }
    const sizes = rawParts.map(p => Number.parseInt(p, 10));
    if (sizes.some(n => !Number.isFinite(n) || n <= 0)) {
      setSplitBlocks([]);
      showAlert('Block sizes must be positive integers.');
      return;
    }
    const blocks = [];
    let offset = 0;
    for (let i = 0; i < sizes.length; i += 1) {
      const size = sizes[i];
      const slice = lines.slice(offset, offset + size);
      blocks.push({ key: `block-${i}`, title: `Block ${i + 1}`, text: slice.join('\n') });
      offset += size;
    }
    if (offset < lines.length) {
      blocks.push({ key: 'remaining', title: 'Remaining', text: lines.slice(offset).join('\n') });
    }
    setSplitBlocks(blocks);
    showAlert(`Created ${blocks.length} block(s).`);
  };

  return (
    <Grid container spacing={2.5} alignItems="stretch">
      <Grid size={{ xs: 12, lg: 6 }} sx={{ display: 'flex' }}>
        <Card variant="outlined" sx={{ flex: 1, height: '100%' }}>
          <CardContent sx={{ height: '100%', display: 'flex' }}>
            <Stack spacing={2} sx={{ flex: 1, minHeight: 0 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography variant="h6" noWrap sx={{ minWidth: 0, flex: 1 }}>
                  Number Formatter
                </Typography>
                <Chip label={`${formatterLinesCount} lines`} size="small" sx={{ ml: 'auto', flexShrink: 0 }} />
              </Stack>
              <Box sx={{ position: 'relative', flex: 1, minHeight: 0 }}>
                <TextField
                  multiline
                  minRows={9}
                  fullWidth
                  value={formatterInput}
                  onChange={event => setFormatterInput(event.target.value)}
                  placeholder={'123\n456\n789'}
                  sx={{
                    ...placeholderSx,
                    height: '100%',
                    '& .MuiInputBase-root': { pr: 6, height: '100%', alignItems: 'flex-start' },
                    '& .MuiInputBase-inputMultiline': { height: '100% !important', overflow: 'auto !important' },
                  }}
                />
                <Tooltip title="Paste">
                  <IconButton size="small" sx={fieldActionSx} onClick={() => handlePaste('formatter')}>
                    <ContentPasteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Clear">
                  <span>
                    <IconButton
                      size="small"
                      sx={fieldActionSecondarySx}
                      onClick={() => {
                        setFormatterInput('');
                        setFormatterOutput('');
                        setFormatterMode('plain');
                      }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <ToggleButtonGroup
                  value={formatterMode}
                  exclusive
                  size="small"
                  sx={{
                    backgroundColor: 'rgba(255, 255, 255, 0.03)',
                    borderRadius: 2,
                    p: 0.35,
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    '& .MuiToggleButton-root': {
                      border: 'none',
                      color: 'rgba(220, 224, 232, 0.88)',
                      px: 2,
                      py: 0.7,
                      lineHeight: 1.1,
                      textTransform: 'none',
                      fontWeight: 700,
                      letterSpacing: 0.2,
                      borderRadius: 1.25,
                    },
                    '& .MuiToggleButton-root:first-of-type': {
                      borderTopLeftRadius: 1.25,
                      borderBottomLeftRadius: 1.25,
                    },
                    '& .MuiToggleButton-root:last-of-type': {
                      borderTopRightRadius: 1.25,
                      borderBottomRightRadius: 1.25,
                    },
                    '& .MuiToggleButton-root.Mui-selected': {
                      backgroundColor: 'primary.main',
                      color: 'primary.contrastText',
                      boxShadow: '0 0 0 1px rgba(124, 156, 255, 0.45) inset',
                      borderRadius: 1.25,
                    },
                    '& .MuiToggleButton-root.Mui-selected:hover': {
                      backgroundColor: 'primary.dark',
                    },
                    '& .MuiToggleButton-root:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.08)',
                    },
                  }}
                  onChange={(_, value) => {
                    if (!value) {
                      return;
                    }
                    setFormatterMode(value);
                  }}
                >
                  <ToggleButton value="plain">Plain</ToggleButton>
                  <ToggleButton value="quoted">With quotes</ToggleButton>
                </ToggleButtonGroup>
              </Stack>
              <Box sx={{ position: 'relative', flex: 1, minHeight: 0 }}>
                <TextField
                  multiline
                  minRows={6}
                  fullWidth
                  value={formatterOutput}
                  slotProps={{ input: { readOnly: true } }}
                  placeholder={formatterPlaceholder}
                  sx={{
                    ...placeholderSx,
                    height: '100%',
                    '& .MuiInputBase-root': { pr: 6, height: '100%', alignItems: 'flex-start' },
                    '& .MuiInputBase-inputMultiline': { height: '100% !important', overflow: 'auto !important' },
                  }}
                />
                <Tooltip title="Copy">
                  <span>
                    <IconButton
                      size="small"
                      sx={fieldActionSx}
                      onClick={() => handleCopy(formatterOutput, 'Nothing to copy yet.')}
                      disabled={!formatterOutput}
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Grid>

      <Grid size={{ xs: 12, lg: 6 }} sx={{ display: 'flex' }}>
        <Card variant="outlined" sx={{ flex: 1, height: '100%' }}>
          <CardContent sx={{ height: '100%', display: 'flex' }}>
            <Stack spacing={2} sx={{ flex: 1, minHeight: 0 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography variant="h6" noWrap sx={{ minWidth: 0, flex: 1 }}>
                  Duplicate Checker
                </Typography>
                <Chip label={`${duplicatesLinesCount} lines`} size="small" sx={{ ml: 'auto', flexShrink: 0 }} />
              </Stack>
              <Box sx={{ position: 'relative', flex: 1, minHeight: 0 }}>
                <TextField
                  multiline
                  minRows={9}
                  fullWidth
                  value={duplicatesInput}
                  onChange={event => setDuplicatesInput(event.target.value)}
                  placeholder={'Example input:\n101021\n830732\n101021\n102988'}
                  sx={{
                    ...placeholderSx,
                    height: '100%',
                    '& .MuiInputBase-root': { pr: 6, height: '100%', alignItems: 'flex-start' },
                    '& .MuiInputBase-inputMultiline': { height: '100% !important', overflow: 'auto !important' },
                  }}
                />
                <Tooltip title="Paste">
                  <IconButton size="small" sx={fieldActionSx} onClick={() => handlePaste('duplicates')}>
                    <ContentPasteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Clear">
                  <span>
                    <IconButton
                      size="small"
                      sx={fieldActionSecondarySx}
                      onClick={() => {
                        setDuplicatesInput('');
                        setDuplicatesOutput('');
                      }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
              <Box sx={{ position: 'relative', flex: 1, minHeight: 0 }}>
                <TextField
                  multiline
                  minRows={6}
                  fullWidth
                  value={duplicatesOutput}
                  slotProps={{ input: { readOnly: true } }}
                  placeholder={'Example output:\nTotal numbers: 4\nUnique numbers: 3\nDuplicates found: 1\n\nDuplicate values: 101021 (x2)'}
                  sx={{
                    ...placeholderSx,
                    height: '100%',
                    '& .MuiInputBase-root': { pr: 6, height: '100%', alignItems: 'flex-start' },
                    '& .MuiInputBase-inputMultiline': { height: '100% !important', overflow: 'auto !important' },
                  }}
                />
                <Tooltip title="Copy">
                  <span>
                    <IconButton
                      size="small"
                      sx={fieldActionSx}
                      onClick={() => handleCopy(duplicatesOutput, 'Nothing to copy yet.')}
                      disabled={!duplicatesOutput}
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Grid>

      <Grid size={{ xs: 12 }} sx={{ display: 'flex' }}>
        <Card variant="outlined" sx={{ flex: 1, width: '100%' }}>
          <CardContent>
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography variant="h6" noWrap sx={{ minWidth: 0, flex: 1 }}>
                  Line Splitter
                </Typography>
                <Chip label={`${splitterLinesCount} lines`} size="small" sx={{ ml: 'auto', flexShrink: 0 }} />
              </Stack>
              <Box sx={{ position: 'relative' }}>
                <TextField
                  multiline
                  minRows={6}
                  fullWidth
                  value={splitterInput}
                  onChange={event => setSplitterInput(event.target.value)}
                  placeholder={'Paste one value per line'}
                  sx={{
                    ...placeholderSx,
                    '& .MuiInputBase-root': { pr: 6, alignItems: 'flex-start' },
                  }}
                />
                <Tooltip title="Paste">
                  <IconButton size="small" sx={fieldActionSx} onClick={() => handlePaste('splitter')}>
                    <ContentPasteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Clear">
                  <span>
                    <IconButton
                      size="small"
                      sx={fieldActionSecondarySx}
                      onClick={() => {
                        setSplitterInput('');
                        setSplitBlocks([]);
                        setSplitPattern('1000,1000,500');
                      }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: { sm: 'center' } }}>
                <TextField
                  size="small"
                  label="Block sizes"
                  value={splitPattern}
                  onChange={event => setSplitPattern(event.target.value)}
                  placeholder="1000, 1000, 500"
                  sx={{ ...placeholderSx, flex: { sm: 1 }, minWidth: { sm: 200 } }}
                />
                <Button variant="contained" onClick={handleSplitIntoBlocks} sx={{ flexShrink: 0, alignSelf: { xs: 'stretch', sm: 'center' } }}>
                  Split into blocks
                </Button>
              </Stack>
              {splitBlocks.length > 0 && (
                <Stack spacing={2}>
                  {splitBlocks.map(block => (
                    <Box key={block.key}>
                      <Stack direction="row" spacing={1} sx={{ mb: 0.75, alignItems: 'center' }}>
                        <Typography variant="subtitle2" color="text.secondary">
                          {block.title}
                        </Typography>
                        <Chip label={`${getTrimmedLines(block.text).length} lines`} size="small" variant="outlined" />
                      </Stack>
                      <Box sx={{ position: 'relative' }}>
                        <TextField
                          multiline
                          minRows={3}
                          fullWidth
                          value={block.text}
                          slotProps={{ input: { readOnly: true } }}
                          sx={{
                            ...placeholderSx,
                            '& .MuiInputBase-root': { pr: 6, alignItems: 'flex-start' },
                          }}
                        />
                        <Tooltip title="Copy block">
                          <span>
                            <IconButton
                              size="small"
                              sx={fieldActionSx}
                              onClick={() => handleCopy(block.text, 'This block is empty.')}
                              disabled={!block.text}
                            >
                              <ContentCopyIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Grid>

      <Snackbar
        open={Boolean(alertText)}
        autoHideDuration={2200}
        onClose={() => setAlertText('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity="info" variant="filled" onClose={() => setAlertText('')}>
          {alertText}
        </Alert>
      </Snackbar>
    </Grid>
  );
}
