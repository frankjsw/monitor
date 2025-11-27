for fid, fid_name in fids.items():
    region_key = fid_name  # fid 显示 product type 名称
    items = fetch_items(fid)
    now_all[region_key] = items

    if region_key not in last:
        msg = [f"📌 首次记录区域 {region_key}"]
        for i in items:
            msg.append(f"{i['name']} 数量：{i['inventory']}")
        messages.append("\n".join(msg))
    else:
        diff = compare(last[region_key], items, region_key)
        if diff:
            messages.append(diff)

    gids = scan_gid_for_fid(fid)
    for gid, zone_name in gids.items():
        region_key = f"{fid_name}&{zone_name}"  # fid+gid显示名称
        items = fetch_items(fid, gid)
        now_all[region_key] = items

        if region_key not in last:
            msg = [f"📌 首次记录区域 {region_key}"]
            for i in items:
                msg.append(f"{i['name']} 数量：{i['inventory']}")
            messages.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items, region_key)
            if diff:
                messages.append(diff)
