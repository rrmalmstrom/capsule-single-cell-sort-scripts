# Critical Instructions for Coding Agent

## Communication Protocol - MANDATORY

**BEFORE implementing each major section, you MUST:**

1. **Explain your understanding** of what you're about to implement
2. **Describe the specific changes** you plan to make
3. **Explain WHY** these changes are needed
4. **Ask for user confirmation** before proceeding
5. **Test and verify** functionality after implementation
6. **Report results** to user before moving to next section

## Major Sections Requiring Pre-Implementation Explanation

### Phase 1: Error Handling Standardization
**BEFORE starting, explain:**
- What `sys.exit(1)` vs `sys.exit()` means
- Which specific functions and line numbers you'll modify
- Why this change is needed for consistency
- Ask: "Should I proceed with standardizing error handling?"

### Phase 2: File Detection System
**BEFORE starting, explain:**
- Current interactive system vs new automatic detection
- How the CSV detection algorithm will work
- What file formats you'll support for custom/additional plates
- How error handling will work when files are missing
- Ask: "Should I proceed with implementing automatic file detection?"

### Phase 3: Database Architecture Changes
**BEFORE starting, explain:**
- Current single-table vs new two-table design
- What data goes in `sample_metadata` vs `individual_plates` tables
- How migration from existing databases will work
- What happens to existing data during migration
- Ask: "Should I proceed with implementing the two-table database architecture?"

### Phase 4: Barcode System Simplification
**BEFORE starting, explain:**
- Current complex system (base + echo + hamilton with collision avoidance)
- New simple system (single base barcode with incremental numbering)
- How continuation numbering will work (T45JK.1, T45JK.2, etc.)
- When echo/hamilton variants are created (print time vs storage time)
- Ask: "Should I proceed with simplifying the barcode generation system?"

### Phase 5: Workflow Integration
**BEFORE starting, explain:**
- How the new main() function workflow will differ from current
- What file detection happens at startup
- How first run vs subsequent run logic changes
- What user interaction is removed vs preserved
- Ask: "Should I proceed with integrating all changes into the main workflow?"

## Testing and Verification Requirements

**After EACH major section implementation:**

1. **Run relevant tests** in sip-lims conda environment
2. **Report test results** (pass/fail with details)
3. **Test with sample data files** if applicable
4. **Verify no breaking changes** to existing functionality
5. **Ask user to confirm** before proceeding to next section

## Specific Verification Points

### After Error Handling Changes
- [ ] Verify all error paths still work correctly
- [ ] Test that fatal errors still terminate properly
- [ ] Confirm laboratory safety messaging is preserved

### After File Detection Implementation
- [ ] Test CSV detection with valid/invalid files
- [ ] Test custom plates file reading
- [ ] Test additional plates file reading
- [ ] Verify error handling for missing files

### After Database Changes
- [ ] Test new table creation
- [ ] Test data migration from existing single-table databases
- [ ] Verify data integrity after migration
- [ ] Test reading/writing to both tables

### After Barcode Simplification
- [ ] Test barcode generation for new projects
- [ ] Test continuation numbering for existing projects
- [ ] Verify BarTender file format compatibility
- [ ] Test echo/hamilton creation at print time

### After Workflow Integration
- [ ] Test complete first run workflow
- [ ] Test complete subsequent run workflow
- [ ] Test all error scenarios
- [ ] Verify no interactive prompts remain

## Communication Examples

### Good Communication (DO THIS):
```
"I'm about to implement the barcode system simplification. Here's my understanding:

CURRENT SYSTEM:
- Generates 3 barcodes per plate: base (ABC12), echo (ABC12E), hamilton (ABC12H)
- Uses collision avoidance with 1000 retry attempts
- Stores all 3 variants in database

NEW SYSTEM:
- Generate 1 base barcode per project (e.g., T45JK)
- Assign incremental numbers: T45JK.1, T45JK.2, T45JK.3
- Store only base barcode and number in database
- Create echo/hamilton variants only when generating BarTender file

CHANGES I'LL MAKE:
1. Replace generate_barcodes() function with generate_simple_barcodes()
2. Remove collision avoidance logic
3. Add incremental numbering logic
4. Update database schema to store plate numbers
5. Modify BarTender file generation to create variants at print time

Does this match your understanding? Should I proceed?"
```

### Bad Communication (DON'T DO THIS):
```
"Implementing barcode changes now..."
[proceeds without explanation or confirmation]
```

## Error Handling During Implementation

**If something doesn't work as expected:**

1. **STOP immediately** - don't try to fix it without user input
2. **Explain what went wrong** in detail
3. **Show error messages** or test failures
4. **Ask for guidance** on how to proceed
5. **Don't make assumptions** about what the user wants

## Environment Requirements - CRITICAL

**ALWAYS:**
- Use `conda activate sip-lims` before any Python operations
- Test in the correct environment
- Verify package availability before proceeding
- Report any environment issues immediately

## File Safety - CRITICAL

**ALWAYS:**
- Test with copies of important files first
- Verify backup/archiving works before modifying originals
- Report any file operation failures immediately
- Don't proceed if file operations fail

## Summary

The key principle is: **COMMUNICATE BEFORE ACTING**

Every major change should be:
1. **Explained** clearly
2. **Confirmed** by user
3. **Implemented** carefully
4. **Tested** thoroughly
5. **Verified** with user

This ensures we stay on track and avoid misunderstandings that could lead to wasted time or broken functionality.