/**
 * Sequence Validator - Validates sequence JSON structure
 * Ensures sequences are properly formatted for backend execution
 */

/**
 * Validate a complete sequence
 * @param {Array} sequence - Array of block objects
 * @param {Array} categories - Available categories
 * @param {Array} prerolls - Available prerolls
 * @returns {Object} - { valid: boolean, errors: string[] }
 */
export const validateSequence = (sequence, categories = [], prerolls = []) => {
  const errors = [];

  // Check if sequence exists and is an array
  if (!sequence) {
    errors.push('Sequence is required');
    return { valid: false, errors };
  }

  if (!Array.isArray(sequence)) {
    errors.push('Sequence must be an array');
    return { valid: false, errors };
  }

  if (sequence.length === 0) {
    errors.push('Sequence must contain at least one block');
    return { valid: false, errors };
  }

  // Validate each block
  sequence.forEach((block, index) => {
    const blockErrors = validateBlock(block, categories, prerolls);
    if (blockErrors.length > 0) {
      errors.push(`Block ${index + 1}: ${blockErrors.join(', ')}`);
    }
  });

  return {
    valid: errors.length === 0,
    errors,
  };
};

/**
 * Validate a single block
 * @param {Object} block - Block object
 * @param {Array} categories - Available categories
 * @param {Array} prerolls - Available prerolls
 * @returns {string[]} - Array of error messages
 */
export const validateBlock = (block, categories = [], prerolls = []) => {
  const errors = [];

  if (!block || typeof block !== 'object') {
    errors.push('Block must be an object');
    return errors;
  }

  // Validate block type
  if (!block.type) {
    errors.push('Block type is required');
    return errors;
  }

  const blockType = String(block.type).toLowerCase();
  if (!['random', 'fixed', 'sequential'].includes(blockType)) {
    errors.push(`Invalid block type: ${block.type}. Must be "random", "fixed", or "sequential"`);
    return errors;
  }

  // Validate random block
  if (blockType === 'random') {
    if (!block.category_id) {
      errors.push('Random block requires category_id');
    } else {
      // Check if category exists
      const categoryExists = categories.some((c) => c.id === block.category_id);
      if (!categoryExists) {
        errors.push(`Category ${block.category_id} not found`);
      }
    }

    if (block.count === undefined || block.count === null) {
      errors.push('Random block requires count');
    } else {
      const count = parseInt(block.count);
      if (isNaN(count) || count < 1) {
        errors.push('Random block count must be at least 1');
      }
      if (count > 10) {
        errors.push('Random block count cannot exceed 10');
      }
    }
  }

  // Validate sequential block (similar to random, but plays in order)
  // Sequential blocks from imports may use category_name instead of category_id
  if (blockType === 'sequential') {
    // Accept either category_id or category_name (for imported sequences)
    if (!block.category_id && !block.category_name) {
      errors.push('Sequential block requires category_id or category_name');
    } else if (block.category_id) {
      // Check if category exists
      const categoryExists = categories.some((c) => c.id === block.category_id);
      if (!categoryExists) {
        errors.push(`Category ${block.category_id} not found`);
      }
    }
    // Note: category_name blocks will be resolved by backend during schedule execution

    // Count is optional for sequential blocks (defaults to 1)
    if (block.count !== undefined && block.count !== null) {
      const count = parseInt(block.count);
      if (isNaN(count) || count < 1) {
        errors.push('Sequential block count must be at least 1');
      }
      if (count > 10) {
        errors.push('Sequential block count cannot exceed 10');
      }
    }
  }

  // Validate fixed block
  if (blockType === 'fixed') {
    if (!block.preroll_ids) {
      errors.push('Fixed block requires preroll_ids array');
    } else if (!Array.isArray(block.preroll_ids)) {
      errors.push('Fixed block preroll_ids must be an array');
    } else if (block.preroll_ids.length === 0) {
      errors.push('Fixed block must have at least one preroll');
    } else {
      // Check if all prerolls exist
      block.preroll_ids.forEach((id) => {
        const prerollExists = prerolls.some((p) => p.id === id);
        if (!prerollExists) {
          errors.push(`Preroll ${id} not found`);
        }
      });
    }
  }

  return errors;
};

/**
 * Sanitize a sequence for backend submission
 * Removes UI-only properties like block IDs
 * @param {Array} sequence - Array of block objects
 * @returns {Array} - Sanitized sequence
 */
export const sanitizeSequence = (sequence) => {
  if (!Array.isArray(sequence)) return [];

  return sequence.map((block) => {
    const sanitized = {
      type: block.type,
    };

    if (block.type === 'random') {
      sanitized.category_id = block.category_id;
      sanitized.count = block.count;
    } else if (block.type === 'fixed') {
      sanitized.preroll_ids = block.preroll_ids || [];
    }

    return sanitized;
  });
};

/**
 * Parse a sequence from JSON string
 * @param {string} sequenceJson - JSON string
 * @returns {Array|null} - Parsed sequence or null if invalid
 */
export const parseSequence = (sequenceJson) => {
  try {
    if (!sequenceJson) return [];
    if (Array.isArray(sequenceJson)) return sequenceJson;
    
    const parsed = JSON.parse(sequenceJson);
    if (!Array.isArray(parsed)) return null;
    
    return parsed;
  } catch (error) {
    console.error('Failed to parse sequence JSON:', error);
    return null;
  }
};

/**
 * Convert sequence to JSON string
 * @param {Array} sequence - Array of block objects
 * @returns {string} - JSON string
 */
export const stringifySequence = (sequence) => {
  try {
    const sanitized = sanitizeSequence(sequence);
    return JSON.stringify(sanitized);
  } catch (error) {
    console.error('Failed to stringify sequence:', error);
    return '[]';
  }
};

/**
 * Check if a sequence has any validation errors
 * @param {Array} sequence - Array of block objects
 * @param {Array} categories - Available categories
 * @param {Array} prerolls - Available prerolls
 * @returns {boolean} - True if valid, false otherwise
 */
export const isSequenceValid = (sequence, categories, prerolls) => {
  const result = validateSequence(sequence, categories, prerolls);
  return result.valid;
};

/**
 * Get human-readable sequence summary
 * @param {Array} sequence - Array of block objects
 * @returns {string} - Summary text
 */
export const getSequenceSummary = (sequence) => {
  if (!Array.isArray(sequence) || sequence.length === 0) {
    return 'Empty sequence';
  }

  const randomBlocks = sequence.filter((b) => b.type === 'random').length;
  const fixedBlocks = sequence.filter((b) => b.type === 'fixed').length;

  const parts = [];
  if (randomBlocks > 0) {
    parts.push(`${randomBlocks} random ${randomBlocks === 1 ? 'block' : 'blocks'}`);
  }
  if (fixedBlocks > 0) {
    parts.push(`${fixedBlocks} fixed ${fixedBlocks === 1 ? 'block' : 'blocks'}`);
  }

  return `${sequence.length} ${sequence.length === 1 ? 'block' : 'blocks'} (${parts.join(', ')})`;
};

/**
 * Estimate total preroll count for a sequence
 * @param {Array} sequence - Array of block objects
 * @returns {Object} - { min: number, max: number }
 */
export const estimatePrerollCount = (sequence) => {
  if (!Array.isArray(sequence)) {
    return { min: 0, max: 0 };
  }

  let count = 0;

  sequence.forEach((block) => {
    if (block.type === 'random') {
      count += block.count || 0;
    } else if (block.type === 'fixed') {
      count += (block.preroll_ids || []).length;
    }
  });

  return { min: count, max: count };
};

/**
 * Clone a sequence with new IDs for UI purposes
 * @param {Array} sequence - Array of block objects
 * @returns {Array} - Cloned sequence with new IDs
 */
export const cloneSequenceWithIds = (sequence) => {
  if (!Array.isArray(sequence)) return [];

  return sequence.map((block, index) => ({
    ...block,
    id: `block-${Date.now()}-${index}-${Math.random().toString(36).substr(2, 9)}`,
  }));
};

export default {
  validateSequence,
  validateBlock,
  sanitizeSequence,
  parseSequence,
  stringifySequence,
  isSequenceValid,
  getSequenceSummary,
  estimatePrerollCount,
  cloneSequenceWithIds,
};
