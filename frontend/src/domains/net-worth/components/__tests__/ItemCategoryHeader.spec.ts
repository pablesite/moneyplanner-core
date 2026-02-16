/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ItemCategoryHeader from '../ItemCategoryHeader.vue';

describe('ItemCategoryHeader', () => {
  it('renders base and percent details', () => {
    const wrapper = mount(ItemCategoryHeader, {
      props: {
        label: 'Activos',
        count: 4,
        totalsLine: '1,200 EUR',
        baseLabel: '1,200 EUR',
        percent: '42',
        showBaseTotal: true,
        showToggle: true,
        expanded: true,
      },
    });

    expect(wrapper.text()).toContain('Activos');
    expect(wrapper.text()).toContain('4');
    expect(wrapper.text()).toContain('1,200 EUR');
    expect(wrapper.text()).toContain('42%');
  });

  it('emits toggle when clicking button', async () => {
    const wrapper = mount(ItemCategoryHeader, {
      props: {
        label: 'Pasivos',
        count: 2,
        totalsLine: '800 EUR',
        baseLabel: null,
        percent: null,
        showBaseTotal: false,
        showToggle: true,
        expanded: false,
      },
    });

    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('toggle')).toHaveLength(1);
  });
});
