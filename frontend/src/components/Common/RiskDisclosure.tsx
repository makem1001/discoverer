/**
 * 发现者（Discoverer）— 风险告知书弹窗
 *
 * 注册流程中的合规组件，要求用户阅读并同意风险告知内容。
 */
import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Checkbox,
  FormControlLabel,
  Button,
  Typography,
} from '@mui/material';

interface RiskDisclosureProps {
  open: boolean;
  onAgree: () => void;
  onClose: () => void;
}

const RISK_ITEMS = [
  '本平台所有分析结果基于历史数据的统计回测，不构成任何形式的投资建议。',
  '历史表现不代表未来收益，策略回测的高收益可能在未来无法复现。',
  '股市交易存在本金损失风险，您应当根据自身的风险承受能力独立做出投资决策。',
  '平台提供的信号发现、策略回测、AI解读等功能仅供学习研究使用。',
  '您应当咨询持牌金融机构的专业投资顾问，获取个性化的投资建议。',
];

const RiskDisclosure: React.FC<RiskDisclosureProps> = ({ open, onAgree, onClose }) => {
  const [agreed, setAgreed] = useState(false);

  const handleAgree = () => {
    setAgreed(false);
    onAgree();
  };

  const handleClose = () => {
    setAgreed(false);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="risk-disclosure-title"
    >
      <DialogTitle id="risk-disclosure-title" sx={{ fontWeight: 600 }}>
        📜 风险告知书
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          在您使用「发现者（Discoverer）」量化回测平台前，请仔细阅读以下风险说明：
        </Typography>
        {RISK_ITEMS.map((item, idx) => (
          <Typography
            key={idx}
            variant="body2"
            sx={{ mb: 1.5, pl: 2, position: 'relative', lineHeight: 1.7 }}
          >
            <span style={{ position: 'absolute', left: 0, fontWeight: 600 }}>
              {idx + 1}.
            </span>
            {item}
          </Typography>
        ))}
      </DialogContent>
      <DialogActions sx={{ flexDirection: 'column', gap: 1, p: 2 }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              size="small"
            />
          }
          label={
            <Typography variant="body2">
              我已阅读并同意以上风险告知内容
            </Typography>
          }
        />
        <Button
          variant="contained"
          onClick={handleAgree}
          disabled={!agreed}
          fullWidth
          sx={{ py: 1 }}
        >
          同意
        </Button>
        <Button variant="text" onClick={handleClose} fullWidth>
          取消
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default RiskDisclosure;
